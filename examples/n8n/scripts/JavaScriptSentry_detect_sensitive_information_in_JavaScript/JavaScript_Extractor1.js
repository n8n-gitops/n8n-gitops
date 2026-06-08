// Extract script URLs from HTML
// Return only JavaScript links
const output = [];
const html = $input.first()?.json?.body || '';
const regex = /<script[^>]*src="([^"]+)"[^>]*>/g;
let match;
while ((match = regex.exec(html)) !== null) {
  output.push({ json: { URL: match[1] } });
}
return output;