import streamlit as st
import plotly.graph_objects as go
from streamlit_option_menu import option_menu
from openai import OpenAI
import json
import time


st.set_page_config(page_title="Travel Companion", page_icon="✈️", layout="wide")


client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
assistant_id = st.secrets["OPENAI_ASSISTANT_ID"]

# Define global state variables
assistant_state = "assistant"
thread_state = "thread"
conversation_state = "conversation"
last_openai_run_state = "last_openai_run"
map_state = "map"
markers_state = "markers"

user_msg_input_key = "input_user_msg"

if (assistant_state not in st.session_state) or (thread_state not in st.session_state):
    st.session_state[assistant_state] = client.beta.assistants.retrieve(assistant_id)
    st.session_state[thread_state] = client.beta.threads.create()

if conversation_state not in st.session_state:
    st.session_state[conversation_state] = []

if last_openai_run_state not in st.session_state:
    st.session_state[last_openai_run_state] = None

if map_state not in st.session_state:
    st.session_state[map_state] = {
        "latitude": 39.949610,
        "longitude": -75.150282,
        "zoom": 13,
    }

if markers_state not in st.session_state:
    st.session_state[markers_state] = None


def update_map_state(latitude, longitude, zoom):
    """OpenAI tool to update map in-app
    """
    st.session_state[map_state] = {
        "latitude": latitude,
        "longitude": longitude,
        "zoom": zoom,
    }
    return "Map updated"


def add_markers_state(latitudes, longitudes, labels):
    """OpenAI tool to update markers in-app
    """
    st.session_state[markers_state] = {
        "lat": latitudes,
        "lon": longitudes,
        "text": labels,
    }
    return "Markers added"


tool_to_function = {
    "update_map": update_map_state,
    "add_markers": add_markers_state,
}

def get_assistant_id():
    return st.session_state[assistant_state].id


def get_thread_id():
    return st.session_state[thread_state].id


def get_run_id():
    return st.session_state[last_openai_run_state].id


def on_text_input(status_placeholder):
    """Callback method for any chat_input value change
    """
    if st.session_state[user_msg_input_key] == "":
        return

    client.beta.threads.messages.create(
        thread_id=get_thread_id(),
        role="user",
        content=st.session_state[user_msg_input_key],
    )
    st.session_state[last_openai_run_state] = client.beta.threads.runs.create(
        assistant_id=get_assistant_id(),
        thread_id=get_thread_id(),
    )

    completed = False

    # Polling
    with status_placeholder.status("Computing Assistant answer") as status_container:
        st.write(f"Launching run {get_run_id()}")

        while not completed:
            run = client.beta.threads.runs.retrieve(
                thread_id=get_thread_id(),
                run_id=get_run_id(),
            )

            if run.status == "requires_action":
                tools_output = []
                for tool_call in run.required_action.submit_tool_outputs.tool_calls:
                    f = tool_call.function
                    print(f)
                    f_name = f.name
                    f_args = json.loads(f.arguments)

                    st.write(f"Launching function {f_name} with args {f_args}")
                    tool_result = tool_to_function[f_name](**f_args)
                    tools_output.append(
                        {
                            "tool_call_id": tool_call.id,
                            "output": tool_result,
                        }
                    )
                st.write(f"Will submit {tools_output}")
                client.beta.threads.runs.submit_tool_outputs(
                    thread_id=get_thread_id(),
                    run_id=get_run_id(),
                    tool_outputs=tools_output,
                )

            if run.status == "completed":
                st.write(f"Completed run {get_run_id()}")
                status_container.update(label="Assistant is done", state="complete")
                completed = True

            else:
                time.sleep(0.1)

    st.session_state[conversation_state] = [
        (m.role, m.content[0].text.value)
        for m in client.beta.threads.messages.list(get_thread_id()).data
    ]


def on_reset_thread():
    client.beta.threads.delete(get_thread_id())
    st.session_state[thread_state] = client.beta.threads.create()
    st.session_state[conversation_state] = []
    st.session_state[last_openai_run_state] = None

#   
    
with st.sidebar:
    selected = option_menu("Navigation", ["home", "contact"], icons=["globe", "envelope"], menu_icon="cast", default_index=0)

# Main page layout
if selected == "home":
    st.title("🌍 Explore with Travel Companion")
    st.write("Ask me anything about your next travel destination!")
    

    tab1 = st.tabs(["Tourist App"])


    left_col, right_col = st.columns(2)

    with left_col:
        with st.container():
            for role, message in st.session_state[conversation_state]:
                with st.chat_message(role):
                    st.write(message)
        status_placeholder = st.empty()

    with right_col:
        fig = go.Figure(
            go.Scattermapbox(
                mode="markers",
            )
        )
        if st.session_state[markers_state] is not None:
            fig.add_trace(
                go.Scattermapbox(
                    mode="markers",
                    marker=go.scattermapbox.Marker(
                        size=24,
                        color="red",
                    ),
                    lat=st.session_state[markers_state]["lat"],
                    lon=st.session_state[markers_state]["lon"],
                    text=st.session_state[markers_state]["text"],
                )
            )
        fig.update_layout(
            margin=dict(l=0, r=0, t=0, b=0),
            mapbox=dict(
                accesstoken=st.secrets["MAPBOX_TOKEN"],
                center=go.layout.mapbox.Center(
                    lat=st.session_state[map_state]["latitude"],
                    lon=st.session_state[map_state]["longitude"],
                ),
                pitch=0,
                zoom=st.session_state[map_state]["zoom"],
            ),
            height=600,
        )
        st.plotly_chart(
            fig, config={"displayModeBar": False}, use_container_width=True, key="plotly"
        )

    st.chat_input(
        placeholder="Ask me anything about your next travel destination!",
        key=user_msg_input_key,
        on_submit=on_text_input,
        args=(status_placeholder,),
    )


elif selected == "contact":
    st.title("Contact Us")
    # Here you add the new visual or information for the contact section
    st.subheader("Get in Touch")
    # Example: Display a contact form
    with st.form("contact_form", clear_on_submit=True):
        name = st.text_input("Name")
        email = st.text_input("Email")
        message = st.text_area("Message")
        submit_button = st.form_submit_button("Send")

        if submit_button:
            # Process the form data, for example, send an email or save the message
            st.success("Thank you for your message!")

    




                    
