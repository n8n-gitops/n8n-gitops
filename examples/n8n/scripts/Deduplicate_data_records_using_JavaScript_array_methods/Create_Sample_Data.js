// Create sample data with intentional duplicates
const usersWithDuplicates = [
  { id: 1, name: "John Doe", email: "user@example.com", department: "Engineering" },
  { id: 2, name: "Jane Smith", email: "user@example.com", department: "Marketing" },
  { id: 3, name: "John Doe", email: "user@example.com", department: "Engineering" }, // Duplicate
  { id: 4, name: "Bob Johnson", email: "user@example.com", department: "Sales" },
  { id: 5, name: "Alice Brown", email: "user@example.com", department: "HR" },
  { id: 6, name: "Jane Smith Updated", email: "user@example.com", department: "Marketing" } // Duplicate
];

// Return the sample data as a single item with usersJson property
return [{
  json: {
    usersJson: JSON.stringify(usersWithDuplicates),
    totalCount: usersWithDuplicates.length,
    message: "Sample data with duplicates created"
  }
}];