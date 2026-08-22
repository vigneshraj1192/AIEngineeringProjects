# 💪 AI Fitness Plan Generator

A Streamlit application that generates personalised weekly workout plans using
Google Gemini.

## Features

- **Smart inputs** — fitness goal, experience level, days/week, equipment, and
  optional injury notes
- **LLM-powered plans** — structured JSON responses parsed into clean UI cards
- **Swap any exercise** — one-click replacement via a second LLM call
- **Persistent state** — plan survives Streamlit reruns
  (`st.session_state`)
- **Markdown export** — download the full plan as a `.md` file
- **Graceful errors** — invalid inputs, API failures, and malformed responses
  all produce friendly messages instead of crashes

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Run the app
streamlit run app.py
```

Enter your **Gemini API key** in the sidebar
(get one free at <https://aistudio.google.com/apikey>).

## Project Structure

```
fitness-plan-generator/
├── app.py              # Streamlit application (all logic in one file)
├── requirements.txt    # Python dependencies
└── README.md           # This file
```
