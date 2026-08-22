"""
AI Fitness Plan Generator — Streamlit Application
===================================================
Generates personalised weekly workout plans using the Gemini LLM.
Each exercise can be individually swapped, and the plan persists across
reruns via st.session_state.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Optional
from groq import Groq
from dotenv import load_dotenv

import streamlit as st

load_dotenv()
# ═══════════════════════════════════════════════════════════════════════════
#  DATA MODELS
# ═══════════════════════════════════════════════════════════════════════════


@dataclass
class Exercise:
    """A single exercise within a training day."""

    name: str
    sets: int
    reps: str
    rest_seconds: int
    notes: str = ""


@dataclass
class DayPlan:
    """One training day consisting of a warm-up, exercises, and cool-down."""

    day: str
    focus: str
    warmup: str
    exercises: list[Exercise] = field(default_factory=list)
    cooldown: str = ""


@dataclass
class WorkoutPlan:
    """The complete multi-day workout plan returned by the LLM."""

    title: str
    summary: str
    days: list[DayPlan] = field(default_factory=list)
    tips: list[str] = field(default_factory=list)


# ═══════════════════════════════════════════════════════════════════════════
#  PROMPT BUILDERS
# ═══════════════════════════════════════════════════════════════════════════


def build_plan_prompt(
    fitness_goal: str,
    experience_level: str,
    days_per_week: int,
    equipment_access: list[str],
    injuries: Optional[str] = None,
) -> str:
    equipment_str = ", ".join(equipment_access)
    injury_section = ""
    if injuries and injuries.strip():
        injury_section = (
            "\n\nINJURIES / LIMITATIONS:\n"
            "The user has the following injuries or limitations that MUST be respected.\n"
            f"{injuries.strip()}\n"
            "Avoid any exercises that could aggravate these conditions and provide "
            "safe alternatives where needed."
        )

    return f"""You are an expert certified personal trainer. Generate a detailed,
personalised weekly workout plan based on the following user profile.

USER PROFILE:
- Fitness Goal: {fitness_goal}
- Experience Level: {experience_level}
- Days Available Per Week: {days_per_week}
- Equipment Access: {equipment_str}{injury_section}

REQUIREMENTS:
1. Create exactly {days_per_week} training day(s).
2. Each day must have a clear focus (e.g. "Upper Body Push", "Legs & Glutes").
3. Each day must include 3-4 exercises appropriate for the user's level and equipment.
4. Include a brief warm-up and cool-down recommendation for each day.
5. Provide 1-2 practical tips at the end.
"""


def build_swap_prompt(
    exercise_name: str,
    day_focus: str,
    fitness_goal: str,
    experience_level: str,
    equipment_access: list[str],
    injuries: Optional[str] = None,
) -> str:
    """Construct a prompt asking the LLM for one alternative exercise.

    Parameters
    ----------
    exercise_name:
        The exercise the user wants to replace.
    day_focus:
        The focus/theme of the training day (e.g. "Pull Day").
    fitness_goal:
        The user's overall goal.
    experience_level:
        Beginner / Intermediate / Advanced.
    equipment_access:
        Available equipment options.
    injuries:
        Free-text injury description (may be *None*).

    Returns
    -------
    str
        The swap prompt.
    """
    equipment_str = ", ".join(equipment_access)
    injury_note = ""
    if injuries and injuries.strip():
        injury_note = (
            f"\nThe user has these limitations: {injuries.strip()}. "
            "The alternative MUST be safe for them."
        )

    return f"""You are an expert certified personal trainer. The user wants to swap
out the exercise "{exercise_name}" from their "{day_focus}" workout day.

USER CONTEXT:
- Fitness Goal: {fitness_goal}
- Experience Level: {experience_level}
- Equipment Access: {equipment_str}{injury_note}

Provide ONE alternative exercise that targets the same muscle group(s) and
fits the user's equipment and level.
"""


# ═══════════════════════════════════════════════════════════════════════════
#  RESPONSE PARSERS
# ═══════════════════════════════════════════════════════════════════════════


def _extract_json(text: str) -> str:
    """Strip optional markdown code fences from LLM output."""
    text = text.strip()
    if "```json" in text:
        text = text.split("```json", 1)[1].split("```", 1)[0]
    elif "```" in text:
        text = text.split("```", 1)[1].split("```", 1)[0]
    return text.strip()


def parse_workout_plan(response_text: str) -> Optional[WorkoutPlan]:
    """Parse raw LLM JSON into a :class:`WorkoutPlan`.

    Returns *None* when parsing fails so the caller can show a friendly
    fallback message instead of crashing.
    """
    try:
        data: dict = json.loads(_extract_json(response_text))

        days: list[DayPlan] = []
        for day_data in data.get("days", []):
            exercises = [
                Exercise(
                    name=ex["name"],
                    sets=int(ex.get("sets", 3)),
                    reps=str(ex.get("reps", "8-12")),
                    rest_seconds=int(ex.get("rest_seconds", 60)),
                    notes=ex.get("notes", ""),
                )
                for ex in day_data.get("exercises", [])
            ]
            days.append(
                DayPlan(
                    day=day_data["day"],
                    focus=day_data.get("focus", ""),
                    warmup=day_data.get("warmup", ""),
                    exercises=exercises,
                    cooldown=day_data.get("cooldown", ""),
                )
            )

        return WorkoutPlan(
            title=data.get("title", "Your Workout Plan"),
            summary=data.get("summary", ""),
            days=days,
            tips=data.get("tips", []),
        )
    except (json.JSONDecodeError, KeyError, TypeError, ValueError):
        return None


def parse_swap_exercise(response_text: str) -> Optional[Exercise]:
    """Parse the LLM swap response into a single :class:`Exercise`.

    Returns *None* on failure.
    """
    try:
        data: dict = json.loads(_extract_json(response_text))
        return Exercise(
            name=data["name"],
            sets=int(data.get("sets", 3)),
            reps=str(data.get("reps", "8-12")),
            rest_seconds=int(data.get("rest_seconds", 60)),
            notes=data.get("notes", ""),
        )
    except (json.JSONDecodeError, KeyError, TypeError, ValueError):
        return None


# ═══════════════════════════════════════════════════════════════════════════
#  LLM INTERACTION
# ═══════════════════════════════════════════════════════════════════════════


def _call_llm(prompt: str) -> str:
    api_key = os.getenv("GROQ_API_KEY")
    
    client = Groq()
    model = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
    system_prompt = f"""
You are an expert certified personal trainer. 
You will create a workout plan for the user based on their goals, experience level, available equipment, and any injuries they may have. Respond ONLY with the workout plan in JSON format. Do not include any additional text or explanation.
{{
    "title": "Workout Plan",
    "summary": "Summary of the workout plan",
    "days": [
        {{
            "day": "Monday",
            "focus": "Workout focus",
            "warmup": "Warmup routine",
            "exercises": [
                {{
                    "name": "Exercise name",
                    "sets": "Number of sets",
                    "reps": "Number of reps",
                    "rest_seconds": "Rest time in seconds",
                    "notes": "Notes about the exercise"
                }}
            ],
            "cooldown": "Cooldown routine"
        }}
    ],
    "tips": [
        "Tip 1"
    ]
}}

If User Request to Swap any excercise Return the JSON Format of that excercise ONLY as below format. Not the full workout plan.
{{ 
    "name": "Exercise name", 
    "sets": "Number of sets", 
    "reps": "Number of reps", 
    "rest_seconds": "Rest time in seconds", 
    "notes": "Notes about the exercise" 
}}

The Response JSON Should be In Proper Valid JSON Format. It Should not be half JSON or Incomplete JSON. It should be Complete JSON.
Include workouts involving Gym Equipments Only when user have access to gym equipments (You will get this information from the user input)
Don't include workouts involving gym equipments when the user doesn't have access to gym equipments
When User has access to Only Home Dumbbells then Include Only Home Dumbbells workotus
When User no equipment then Include Only Bodyweight workouts
Keep exercise notes concise, maximum 10 words per exercise.
Keep warm-up and cool-down descriptions concise.

When User has any injuries then Don't include any exercises that are related to that injury or aggrevate the injury
Example:
Injury: Knee Pain
Don't include: Squats, Lunges, Leg Press
Include: Glute Bridges, Hamstring Curls, Calf Raises

Include the excercises according to the fitness goal and experience level
"""
    completion = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ],
        temperature=0.3,
        max_tokens=20000
    )
    print(completion.choices[0].finish_reason)
    return completion.choices[0].message.content


def _classify_api_error(exc: Exception) -> str:
    """Return a user-friendly message based on common API failure modes."""
    msg = str(exc).lower()
    if "api key" in msg or "unauthorized" in msg or "403" in msg:
        return "❌ Invalid API key. Please check your Grow API key and try again."
    if "rate" in msg or "429" in msg or "quota" in msg:
        return "⏳ Rate limit reached. Please wait a moment and try again."
    if "timeout" in msg or "connection" in msg:
        return "🌐 Network error. Please check your internet connection and try again."
    return f"❌ API call failed: {exc}"


def generate_plan(
    fitness_goal: str,
    experience_level: str,
    days_per_week: int,
    equipment_access: list[str],
    injuries: Optional[str],
    api_key: str,
) -> WorkoutPlan:
    """High-level function: validate inputs → call LLM → parse response.

    Parameters
    ----------
    fitness_goal:
        The user's selected fitness goal.
    experience_level:
        Beginner / Intermediate / Advanced.
    days_per_week:
        Number of available training days (1-7).
    equipment_access:
        List of equipment the user has access to.
    injuries:
        Free-text injuries/limitations or *None*.

    Returns
    -------
    WorkoutPlan
        The fully parsed plan.

    Raises
    ------
    ValueError
        On invalid / missing inputs.
    ConnectionError
        On API call failure.
    RuntimeError
        On empty or unparseable LLM response.
    """
    # ── Input validation ────────────────────────────────────────────────
    if days_per_week < 1 or days_per_week > 7:
        raise ValueError("Please select between 1 and 7 days per week.")
    if not equipment_access:
        raise ValueError("Please select at least one equipment option.")
    
    # ── Build prompt & call LLM ─────────────────────────────────────────
    prompt = build_plan_prompt(
        fitness_goal=fitness_goal,
        experience_level=experience_level,
        days_per_week=days_per_week,
        equipment_access=equipment_access,
        injuries=injuries,
    )

    try:
        response_text = _call_llm(prompt)
    except Exception as exc:
        raise ConnectionError(_classify_api_error(exc)) from exc

    # ── Parse response ──────────────────────────────────────────────────
    if not response_text.strip():
        raise RuntimeError(
            "The AI returned an empty response. Please try generating again."
        )
    
    plan = parse_workout_plan(response_text)
    if plan is None:
        raise RuntimeError(
            "The AI response could not be parsed into a valid workout plan. "
            "Please try again."
        )
    if not plan.days:
        raise RuntimeError(
            "The AI generated a plan with no training days. Please try again."
        )

    return plan


def swap_exercise(
    exercise_name: str,
    day_focus: str,
    fitness_goal: str,
    experience_level: str,
    equipment_access: list[str],
    injuries: Optional[str],
    api_key: str,
) -> Exercise:
    """Replace a single exercise by asking the LLM for an alternative.

    Parameters
    ----------
    exercise_name:
        Name of the exercise to swap out.
    day_focus:
        The focus of the day that contains the exercise.
    fitness_goal:
        The user's overall fitness goal.
    experience_level:
        Beginner / Intermediate / Advanced.
    equipment_access:
        Available equipment.
    injuries:
        Injury/limitation text or *None*.

    Returns
    -------
    Exercise
        The replacement exercise.

    Raises
    ------
    ConnectionError
        On API failure.
    RuntimeError
        On empty / unparseable response.
    """
    prompt = build_swap_prompt(
        exercise_name=exercise_name,
        day_focus=day_focus,
        fitness_goal=fitness_goal,
        experience_level=experience_level,
        equipment_access=equipment_access,
        injuries=injuries,
    )

    try:
        response_text = _call_llm(prompt)
    except Exception as exc:
        raise ConnectionError(_classify_api_error(exc)) from exc

    if not response_text.strip():
        raise RuntimeError(
            "The AI returned an empty response for the swap. Please try again."
        )

    exercise = parse_swap_exercise(response_text)
    if exercise is None:
        raise RuntimeError(
            "Could not parse the alternative exercise. Please try again."
        )

    return exercise


# ═══════════════════════════════════════════════════════════════════════════
#  MARKDOWN EXPORT
# ═══════════════════════════════════════════════════════════════════════════


def plan_to_markdown(plan: WorkoutPlan) -> str:
    """Convert a :class:`WorkoutPlan` to a downloadable Markdown string."""
    lines: list[str] = [f"# {plan.title}", "", plan.summary, ""]

    for day in plan.days:
        lines += [f"## {day.day}: {day.focus}", ""]
        if day.warmup:
            lines += [f"**🔥 Warm-up:** {day.warmup}", ""]

        lines += [
            "| # | Exercise | Sets | Reps | Rest | Notes |",
            "|---|----------|------|------|------|-------|",
        ]
        for i, ex in enumerate(day.exercises, 1):
            notes = ex.notes or "—"
            lines.append(
                f"| {i} | {ex.name} | {ex.sets} | {ex.reps} "
                f"| {ex.rest_seconds}s | {notes} |"
            )
        lines.append("")

        if day.cooldown:
            lines += [f"**🧊 Cool-down:** {day.cooldown}", ""]
        lines += ["---", ""]

    if plan.tips:
        lines += ["## 💡 Tips", ""]
        for tip in plan.tips:
            lines.append(f"- {tip}")
        lines.append("")

    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════
#  STREAMLIT UI
# ═══════════════════════════════════════════════════════════════════════════

st.set_page_config(
    page_title="AI Fitness Plan Generator",
    page_icon="💪",
    layout="wide",
)

st.title("💪 Fitness Plan Generator")
st.caption("Get a personalised workout plan")


# ── API key from environment ────────────────────────────────────────────
api_key: str = os.environ.get("GROQ_API_KEY", "")

# ── Session state defaults ──────────────────────────────────────────────
if "plan" not in st.session_state:
    st.session_state.plan: Optional[WorkoutPlan] = None  # type: ignore[annotation-unchecked]
if "generated" not in st.session_state:
    st.session_state.generated: bool = False  # type: ignore[annotation-unchecked]

# ── Input form ──────────────────────────────────────────────────────────
st.subheader("📋 Your Profile")

col1, col2 = st.columns(2)

with col1:
    fitness_goal: str = st.selectbox(
        "🎯 Fitness Goal",
        options=["Build muscle", "Lose fat", "General fitness", "Improve endurance"],
    )  # type: ignore[assignment]
    days_per_week: int = st.slider(
        "📅 Days Available Per Week",
        min_value=1,
        max_value=7,
        value=4,
    )

with col2:
    experience_level: str = st.selectbox(
        "📊 Experience Level",
        options=["Beginner", "Intermediate", "Advanced"],
    )  # type: ignore[assignment]
    equipment_access: list[str] = st.multiselect(
        "🏋️ Equipment Access",
        options=["No equipment", "Home dumbbells", "Full gym"],
        default=["Full gym"],
    )

injuries: str = st.text_area(
    "🩹 Injuries or Limitations *(optional)*",
    placeholder='e.g. "bad knees", "no overhead pressing", "lower back pain"',
    height=80,
)

# ── Generate / Regenerate button ────────────────────────────────────────
button_label = (
    "🔄 Regenerate Plan" if st.session_state.generated else "✨ Generate Plan"
)

if st.button(button_label, type="primary", use_container_width=True):
    try:
        with st.spinner("🧠 Crafting your personalised plan …"):
            plan = generate_plan(
                fitness_goal=fitness_goal,
                experience_level=experience_level,
                days_per_week=days_per_week,
                equipment_access=equipment_access,
                injuries=injuries or None,
                api_key=api_key,
            )
            st.session_state.plan = plan
            st.session_state.generated = True
            st.rerun()
    except ValueError as exc:
        st.warning(str(exc))
    except ConnectionError as exc:
        st.error(str(exc))
    except RuntimeError as exc:
        st.error(str(exc))

# ── Display persisted plan ──────────────────────────────────────────────
if st.session_state.plan is not None:
    plan: WorkoutPlan = st.session_state.plan  # type: ignore[no-redef]

    st.divider()
    st.header(plan.title)
    st.info(plan.summary)

    # Download button
    md_content = plan_to_markdown(plan)
    st.download_button(
        label="📥 Download Plan (.md)",
        data=md_content,
        file_name="workout_plan.md",
        mime="text/markdown",
    )

    # ── Render each training day ────────────────────────────────────────
    for day_idx, day in enumerate(plan.days):
        with st.expander(f"**{day.day}: {day.focus}**", expanded=True):
            if day.warmup:
                st.markdown(f"🔥 **Warm-up:** {day.warmup}")

            for ex_idx, exercise in enumerate(day.exercises):
                col_info, col_btn = st.columns([5, 1])

                with col_info:
                    st.markdown(
                        f"**{ex_idx + 1}. {exercise.name}** — "
                        f"`{exercise.sets} sets × {exercise.reps} reps` · "
                        f"Rest {exercise.rest_seconds}s"
                    )
                    if exercise.notes:
                        st.caption(f"💡 {exercise.notes}")

                with col_btn:
                    if st.button("🔀 Swap", key=f"swap_{day_idx}_{ex_idx}"):
                        try:
                            with st.spinner(
                                f"Finding alternative for {exercise.name}…"
                            ):
                                new_ex = swap_exercise(
                                    exercise_name=exercise.name,
                                    day_focus=day.focus,
                                    fitness_goal=fitness_goal,
                                    experience_level=experience_level,
                                    equipment_access=equipment_access,
                                    injuries=injuries or None,
                                    api_key=api_key,
                                )
                                st.session_state.plan.days[day_idx].exercises[
                                    ex_idx
                                ] = new_ex
                                st.rerun()
                        except (ConnectionError, RuntimeError) as exc:
                            st.error(str(exc))

            if day.cooldown:
                st.markdown(f"🧊 **Cool-down:** {day.cooldown}")

    # ── Tips ────────────────────────────────────────────────────────────
    if plan.tips:
        st.subheader("💡 Pro Tips")
        for tip in plan.tips:
            st.markdown(f"- {tip}")
