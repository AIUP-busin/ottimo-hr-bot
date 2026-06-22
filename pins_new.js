// api/pins.js — Employee PIN registration & lookup
if (!global._pins)  global._pins  = {}; // { pin: {empId,name,position,tgId} }
if (!global._tgmap) global._tgmap = {}; // { tgId: empId }

module.exports = async (req, res) => {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET,POST,PATCH,OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');
  if (req.method === 'OPTIONS') return res.status(200).end();

  // POST {pin, empId, name, position} → register PIN
  if (req.method === 'POST') {
    const { pin, empId, name, position } = req.body;
    if (!pin || !empId || !name)
      return res.status(400).json({ ok: false, error: 'pin, empId, name required' });
    global._pins[String(pin)] = { empId, name, position: position || '', tgId: null };
    return res.json({ ok: true });
  }

  // GET ?pin=XXXX  → employee info by PIN
  // GET ?tgId=XXXX → employee info by Telegram ID
  if (req.method === 'GET') {
    const { pin, tgId } = req.query;
    if (pin) {
      const emp = global._pins[String(pin)];
      if (!emp) return res.json({ ok: false, error: 'PIN topilmadi' });
      return res.json({ ok: true, emp });
    }
    if (tgId) {
      const empId = global._tgmap[String(tgId)];
      if (!empId) return res.json({ ok: false, registered: false });
      const emp = Object.values(global._pins).find(e => e.empId === empId);
      return res.json({ ok: true, registered: true, emp });
    }
    return res.status(400).json({ ok: false, error: 'pin yoki tgId kerak' });
  }

  res.status(405).json({ ok: false });
};
