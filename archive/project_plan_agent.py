import uuid
import pandas as pd
from typing import TypedDict, Dict
from langchain.tools import tool
from langgraph.graph import StateGraph
from langgraph.checkpoint.memory import MemorySaver
from archive.plan_builder import Plan
import logging

# ---- CONFIGURE LOGGING ----
# logging.basicConfig(level=logging.DEBUG)
# logger = logging.getLogger(__name__)

# ---- DEFINE STATE ----
class AgentState(TypedDict):
    user_input: str
    plan_params: Dict
    created_plan: str   # pd.DataFrame
    update_options: list

# ---- MEMORY ----
memory = MemorySaver()

# ---- TOOLS ----
# @tool
def run_plan_builder(plan_params: dict) -> pd.DataFrame:
    """Takes plan params and returns plan built for those params."""
    plan = Plan()
    if not plan_params:
        # Set up default values for plan parameters, just for testing
        plan.idea = "PSTRATEGIC-I-2278"
        plan.rally_theme = "ST20101"
        plan.project_type = "Foundational-PCP Assignment"
        plan.idea_name = "PCP Assignment 2025 carry over"
        plan.BDL = "Jason Merckling"
        plan.RDL = "Chris Capewell"
        plan.business_owner = "Gina Milana"
    else:
        # Populate params from user-provided values
        plan.idea = plan_params.get("plan idea", "PSTRATEGIC-I-2278")
        plan.rally_theme = plan_params.get("rally theme", "ST20101")
        plan.project_type = plan_params.get("project type", "Foundational-PCP Assignment")
        plan.idea_name = plan_params.get("idea name", "PCP Assignment 2025 carry over")
        plan.BDL = plan_params.get("BDL", "Jason Merckling")
        plan.RDL = plan_params.get("RDL", "Chris Capewell")
        plan.business_owner = plan_params.get("business owner", "Gina Milana")

    plan.load_plan_template()
    plan.build_plan()
    return plan.new_plan

def chat_bot(state: AgentState) -> AgentState:
    """This agent should keep communication with end user to get plan parameters."""
    if state["created_plan"] is None:
        plan_params = {}
        # logger.info("CREATING NEW PROJECT PLAN")
        # logger.info("Please provide the necessary parameters for the plan. Default parameters will be used if none are provided.")
        user_input = "default input"  # Replace input() with a default value or parameter
        default_params_message = """
        Aha idea is "PSTRATEGIC-I-2278". The Rally Strategic Theme is ST20101 
        and this is a Foundational-PCP Assignment project type. The Aha Idea Name is "PCP Assignment 2025 carry over". 
        Members of the core project team are BDL = "Jason Merckling", RDL = "Chris Capewell", Business owner = "Gina Milana"
        """
        # logger.info("DEFAULT PARAMETERS IN USE:")
        # logger.info(default_params_message)

        return {"user_input": user_input, "plan_params": plan_params, "created_plan": state["created_plan"], "update_options": []}

def handle_updates(update_options: list):
    """Handles updates based on selected options and prints messages."""
    for option in update_options:
        # logger.info(f"Handling update: {option}")
        print(f"Handling update: {option}")
        # Add your update logic here

def project_plan_agent(state: AgentState) -> AgentState:
    """Creates new plan based on parameters that User provided and handles updates."""
    plan_params = state["plan_params"]
    plan = run_plan_builder(plan_params)
    # logger.info("New plan created")
    # logger.debug(plan)
    res = "New Plan Created"

    # Handle updates if any
    if state["update_options"]:
        handle_updates(state["update_options"])

    return {"created_plan": res, "update_options": state["update_options"]}

# ---- BUILD LANGGRAPH WORKFLOW ----
workflow = StateGraph(AgentState)
workflow.add_node("chat_bot", chat_bot)
workflow.add_node("project_plan_agent", project_plan_agent)

# Define edges
workflow.set_entry_point("chat_bot")
workflow.add_edge("chat_bot", "project_plan_agent")

# Compile workflow
graph = workflow.compile(checkpointer=memory)

# ---- RUN WORKFLOW ----
config = {"configurable": {"thread_id": str(uuid.uuid4())}}
output = graph.stream({"created_plan": None, "user_input": "", "plan_params": {}, "update_options": []}, config=config)

# for state in output:
#     logger.info("Workflow state:")
#     logger.debug(state)
