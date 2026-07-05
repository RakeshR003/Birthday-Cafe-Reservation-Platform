// static/js/availability.js
async function checkAvailability(decorationId, date, time) {
  const params = new URLSearchParams({decoration_id: decorationId, date: date, time: time});
  const resp = await fetch('/api/check_availability?' + params.toString());
  if (!resp.ok) {
    const text = await resp.text().catch(() => '');
    throw new Error('Availability API error: ' + text);
  }
  return resp.json();
}
