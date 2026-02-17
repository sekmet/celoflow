
import os
import logging
from dotenv import load_dotenv
from agents import Agent as SDKAgent
from contextwise.models import AzureForgeModel
from contextwise import Agent

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("debug")

load_dotenv()

def debug_sdk_agent():
    print("--- Debugging SDK Agent ---")
    try:
        model = AzureForgeModel("gpt-5.2-chat")
        print(f"Model created: {model}, type: {type(model)}")
        
        # Try to resolve model ID like contextwise does
        model_id = model.id if hasattr(model, 'id') else str(model)
        print(f"Resolved model ID: {model_id}")

        agent = SDKAgent(
            name="Test Agent",
            instructions="You are a test.",
            model=model_id,
        )
        print(f"SDK Agent created: {agent}, type: {type(agent)}")
        if agent is None:
            print("CRITICAL: SDK Agent is None!")
        else:
            print("SDK Agent is valid.")
            
    except Exception as e:
        print(f"Error creating SDK Agent: {e}")
        import traceback
        traceback.print_exc()

from contextwise.lib.base import AgentPlugin
from agents import Agent as SDKAgent

class DummyPlugin(AgentPlugin):
    name = "dummy"
    def configure_agent(self, agent: SDKAgent) -> SDKAgent:
        print("Configuring agent with dummy plugin")
        return agent

def debug_contextwise_agent():
    print("\n--- Debugging Contextwise Agent ---")
    try:
        model = AzureForgeModel("gpt-5.2-chat")
        plugin = DummyPlugin()
        agent = Agent(
            name="Contextwise Agent",
            model=model,
            instructions="Test",
            plugins=[plugin]
        )
        print(f"Contextwise Agent created: {agent}")
    except Exception as e:
        print(f"Error creating Contextwise Agent: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    debug_sdk_agent()
    debug_contextwise_agent()
