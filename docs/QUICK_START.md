# Quick Start Guide - 100AC

## Overview
100AC is a distributed system of 100 specialized micro agents designed to help navigate financial markets. This guide will help you get started quickly.

## Prerequisites
- Python 3.10 or higher
- pip (Python package manager)
- Optional: Anthropic API key for Claude integration

## Installation

### 1. Navigate to the project directory
```bash
cd /Users/knandula/work/roborev/100AC
```

### 2. Create a virtual environment
```bash
python -m venv venv
source venv/bin/activate  # On macOS/Linux
# OR
venv\Scripts\activate     # On Windows
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure environment (optional)
```bash
cp .env.example .env
# Edit .env and add your ANTHROPIC_API_KEY if you have one
```

## Running the System

### Run the demo
```bash
python main.py
```

This will:
1. Initialize the message bus
2. Register test agents
3. Run communication tests
4. Display system status
5. Gracefully shutdown

### Run tests
```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=. --cov-report=html

# Run specific test file
pytest tests/test_message_bus.py -v
```

## Project Structure

```
100AC/
├── agents/              # Agent implementations
│   ├── base_agent.py   # Base class template
│   ├── test_agent.py   # Example agent
│   ├── registry.py     # Agent registry
│   └── orchestrator.py # Workflow manager
├── shared/              # Shared utilities
│   ├── message_bus.py  # Messaging system
│   ├── data_models.py  # Data structures
│   ├── config.py       # Configuration
│   └── utils.py        # Helpers
├── tests/              # Test suite
├── configs/            # YAML configs
├── docs/               # Documentation
├── main.py            # Entry point
└── requirements.txt   # Dependencies
```

## Creating Your First Agent

### 1. Create a new agent file
```python
# agents/my_agent.py

from agents.base_agent import BaseAgent
from shared.data_models import AgentMetadata, AgentCapability, Message

class MyAgent(BaseAgent):
    def get_metadata(self) -> AgentMetadata:
        return AgentMetadata(
            agent_id="my_agent",
            name="My Custom Agent",
            description="My agent description",
            category="data",  # or technical, fundamental, risk, etc.
            capabilities=[
                AgentCapability(
                    name="do_something",
                    description="Does something useful",
                    parameters={"input": "str"},
                    returns="Dict[str, Any]",
                )
            ],
            subscribes_to=["input_topic"],
            publishes_to=["output_topic"],
        )
    
    async def process_request(self, message: Message) -> dict:
        # Handle incoming requests
        if message.topic == "do_something":
            input_data = message.data.get("input", "")
            result = f"Processed: {input_data}"
            return {"result": result, "status": "success"}
        
        return {"error": "Unknown action"}
```

### 2. Register your agent
```python
# In main.py or your script
from agents.my_agent import MyAgent
from agents.registry import get_registry

# Create and register
my_agent = MyAgent()
registry = get_registry()
registry.register(my_agent)

# Start the agent
await my_agent.start()
```

### 3. Use your agent
```python
from agents.orchestrator import get_orchestrator

orchestrator = get_orchestrator()

# Send a request
result = await orchestrator.execute_simple_request(
    agent_id="my_agent",
    action="do_something",
    parameters={"input": "test data"},
    timeout=5.0,
)

print(result)
```

## Configuration

### Environment Variables (.env)
```bash
# Claude AI
ANTHROPIC_API_KEY=your_api_key_here

# Agent Configuration
AGENT_LOG_LEVEL=INFO
MESSAGE_BUS_TYPE=memory
MESSAGE_RETENTION_SECONDS=3600

# Development
DEBUG=false
ENVIRONMENT=development
```

### Agent Registry (configs/agent_registry.yaml)
```yaml
agents:
  - agent_id: my_agent
    name: My Agent
    description: Agent description
    category: data
    enabled: true
    capabilities:
      - name: capability_name
        description: What it does
    subscribes_to:
      - topic1
    publishes_to:
      - topic2
```

## Common Tasks

### Send a message between agents
```python
# From within an agent
await self.publish_event(
    topic="market_update",
    data={"symbol": "AAPL", "price": 150.0}
)
```

### Request data from another agent
```python
# From within an agent
response = await self.request_from_agent(
    to_agent="market_data_fetcher",
    topic="get_price",
    data={"symbol": "AAPL"},
    timeout=5.0,
)
price = response["price"]
```

### Create a workflow
```python
from agents.orchestrator import get_orchestrator

orchestrator = get_orchestrator()

workflow = orchestrator.create_workflow(
    name="Simple Analysis",
    description="Fetch and analyze data",
    steps=[
        {
            "agent_id": "data_fetcher",
            "action": "fetch",
            "parameters": {"symbol": "AAPL"},
        },
        {
            "agent_id": "analyzer",
            "action": "analyze",
            "parameters": {},  # Will receive previous step's output
        }
    ]
)

result = await orchestrator.execute_workflow(workflow)
```

## Debugging

### Enable debug logging
```bash
# In .env
DEBUG=true
AGENT_LOG_LEVEL=DEBUG
```

### View message history
```python
from shared.message_bus import get_message_bus

bus = get_message_bus()
history = bus.get_history(topic="your_topic", limit=100)
for msg in history:
    print(msg)
```

### Check agent health
```python
from agents.registry import get_registry

registry = get_registry()
for agent in registry.get_all_agents():
    health = agent.get_health()
    print(f"{agent.agent_id}: {health.status} - "
          f"{health.messages_processed} messages processed")
```

## Next Steps

1. **Read the spec**: Check `100AC_spec.md` for the complete agent list
2. **Phase 1 Report**: See `docs/PHASE1_COMPLETION_REPORT.md`
3. **Build more agents**: Start with data collection agents (Category 1)
4. **Add tests**: Create tests for your agents
5. **Contribute**: Follow the development guidelines

## Getting Help

- Check the documentation in `docs/`
- Review existing agents for examples
- Read the test files for usage patterns
- Review Phase 1 completion report for architecture details

## What's Working

✅ Message bus communication  
✅ Agent registration and discovery  
✅ Event publishing and subscription  
✅ Health monitoring  
✅ Configuration management  
✅ Test infrastructure  

## What's Next (Phase 2)

- Implement real financial market agents
- Add data persistence (SQLite)
- Claude AI integration for intelligent agents
- More comprehensive workflows
- API integrations for market data

---

Happy coding! 🚀
