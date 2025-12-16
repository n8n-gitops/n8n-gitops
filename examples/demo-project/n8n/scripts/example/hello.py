"""Example Python script for n8n Code node."""

def process_item(item):
    """Process a single item from n8n input.

    Args:
        item: Input item from previous node

    Returns:
        Processed result
    """
    name = item.get("name", "World")
    return {
        "greeting": f"Hello, {name}!",
        "processed_at": "2025-12-16",
        "status": "success"
    }

# n8n Code node execution
# Access input items via 'items' variable
results = [process_item(item.json) for item in items]
return results
