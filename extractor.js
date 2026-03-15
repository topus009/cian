const fs = require('fs');

const dataStr = fs.readFileSync('data/apartments.json', 'utf8');
const apartments = JSON.parse(dataStr);

const hiddenStr = fs.readFileSync('data/hidden_ids.js', 'utf8');
const arrMatch = hiddenStr.match(/\[([\s\S]*?)\]/);
let hiddenIds = [];
if (arrMatch) {
    // using eval is ok for local script
    hiddenIds = eval('[' + arrMatch[1] + ']');
}

const visibleApts = apartments.filter(apt => {
    const m = apt.url.match(/flat\/(\d+)/);
    if (!m) return true;
    return !hiddenIds.includes(m[1]);
});

console.log("Found visible apartments: " + visibleApts.length);

const aptsInfo = visibleApts.map(a => {
    return {
        url: a.url,
        title: a.title,
        price: a.price,
        address: a.address,
        area: a.total_area,
        desc: a.description
    }
});

fs.writeFileSync('visibleApts.json', JSON.stringify(aptsInfo, null, 2));

