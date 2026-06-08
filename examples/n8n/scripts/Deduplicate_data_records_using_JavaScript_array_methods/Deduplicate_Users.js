// 🧱 Data Deduplication Code Node
// Use Case: Clean up duplicates before inserting into DB or CRM

// Parse the users JSON from the previous node
const users = JSON.parse(items[0].json.usersJson);

// Deduplicate users based on email address
// This keeps the first occurrence of each unique email
const uniqueUsers = users.filter(
  (user, index, self) => 
    index === self.findIndex(u => u.email === user.email)
);

// Log the deduplication results
console.log(`Original count: ${users.length}`);
console.log(`Deduplicated count: ${uniqueUsers.length}`);
console.log(`Duplicates removed: ${users.length - uniqueUsers.length}`);

// Return the deduplicated users in n8n format
// Each user becomes a separate item in the workflow
return uniqueUsers.map(user => ({ json: user }));