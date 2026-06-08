// Display the final results with statistics
const currentItems = items;
const uniqueCount = currentItems.length;

// Create a summary of the deduplication process
const summary = {
  deduplicated_users: currentItems.map(item => item.json),
  statistics: {
    unique_users_count: uniqueCount,
    process_completed: true,
    timestamp: new Date().toISOString()
  },
  message: `Successfully deduplicated data - ${uniqueCount} unique users remaining`
};

return [{ json: summary }];