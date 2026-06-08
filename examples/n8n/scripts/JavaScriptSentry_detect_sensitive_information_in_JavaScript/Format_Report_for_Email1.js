const aiReport = $json.output || 'No AI report.';

return [{
  json: {
    htmlReport: `<html><body><h1>AI Report</h1><pre>${aiReport}</pre></body></html>`
  }
}];