# 💪 AI Fitness Plan Generator

A Streamlit application that generates personalised weekly workout plans using
Groq.

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

# 2. Create your local environment file
copy .env.example .env

# 3. Run the app
streamlit run app.py
```

Add your Groq API key to `.env` as `GROQ_API_KEY` (get one at
<https://console.groq.com/keys>). `.env` is ignored by Git; do not commit your
API key. `GROQ_MODEL` is optional and defaults to `openai/gpt-oss-120b`.

## Project Structure

```
fitness-plan-generator/
├── app.py              # Streamlit application (all logic in one file)
├── requirements.txt    # Python dependencies
└── README.md           # This file
```
