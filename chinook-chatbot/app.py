"""Streamlit chat UI for the Chinook intelligent wrapper.

Run from this folder:
    pip install -r requirements.txt
    cp .env.example .env   # then set OPENAI_API_KEY
    streamlit run app.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from chinook_bot.agent import BotReply, ChinookAgent
from chinook_bot.db import DEFAULT_SQL, initialize_database
from chinook_bot.schema import TABLES

st.set_page_config(page_title="Chinook store bot", page_icon="♪", layout="wide")


@st.cache_resource(show_spinner="Loading Chinook SQLite database…")
def get_agent() -> ChinookAgent:
    initialize_database()
    return ChinookAgent()


def render_reply(reply: BotReply) -> None:
    st.markdown(reply.text)
    if reply.sql:
        with st.expander("SQL used"):
            st.code(reply.sql, language="sql")
            if reply.rows:
                st.dataframe(reply.rows, use_container_width=True)
            elif reply.error:
                st.caption("Query did not return rows.")
    if reply.hits:
        with st.expander("Name matches"):
            st.table(reply.hits)
    if reply.error:
        st.caption(f"Details: {reply.error}")


def main() -> None:
    st.title("Chinook store assistant")
    st.caption(
        "Answers only from the Chinook sample database "
        f"(`{DEFAULT_SQL.name}`). Catalog, playlists, customers, employees, invoices."
    )

    with st.sidebar:
        st.subheader("What this bot knows")
        st.markdown(
            "Loaded from the Chinook SQL script into a local SQLite file. "
            "It will not use outside music knowledge."
        )
        st.markdown("**Tables**")
        for name, spec in TABLES.items():
            cols = ", ".join(spec["columns"].keys())
            st.markdown(f"- `{name}` — {cols}")
        st.divider()
        st.markdown(
            "Example questions:\n"
            "- Who are the top 5 customers by invoice total?\n"
            "- How many tracks are in the Rock genre?\n"
            "- Which albums does AC/DC have?\n"
            "- Who is the support rep for customer Helena?\n"
        )

    if "messages" not in st.session_state:
        st.session_state.messages = []

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            if message["role"] == "assistant" and message.get("reply"):
                render_reply(message["reply"])
            else:
                st.markdown(message["content"])

    prompt = st.chat_input("Ask about Chinook artists, sales, playlists, customers…")
    if not prompt:
        return

    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    history = [
        {"role": m["role"], "content": m["content"]}
        for m in st.session_state.messages[:-1]
        if m.get("content")
    ]

    with st.chat_message("assistant"):
        try:
            with st.spinner("Querying Chinook…"):
                reply = get_agent().ask(prompt, history)
        except RuntimeError as exc:
            reply = BotReply(text=str(exc), intent="error", error=str(exc))
        render_reply(reply)

    st.session_state.messages.append(
        {"role": "assistant", "content": reply.text, "reply": reply}
    )


if __name__ == "__main__":
    main()
