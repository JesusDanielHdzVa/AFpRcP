
const express = require('express');
const sqlite3 = require('sqlite3').verbose();
const bodyParser = require('body-parser');
const cors = require('cors');
const path = require('path');

const app = express();
const PORT = 3000;


app.use(cors());
app.use(bodyParser.json());
app.use(express.static('public'));


const db = new sqlite3.Database('./mi_base_datos.db', (err) => {
    if (err) console.error(err.message);
    console.log('Conectado a la base de datos SQLite.');
});


db.run(`CREATE TABLE IF NOT EXISTS ventas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    mes TEXT,
    cantidad INTEGER
)`);




app.post('/api/ventas', (req, res) => {
    const { mes, cantidad } = req.body;
    const sql = `INSERT INTO ventas (mes, cantidad) VALUES (?, ?)`;
    db.run(sql, [mes, cantidad], function(err) {
        if (err) return res.status(400).json({ error: err.message });
        res.json({ id: this.lastID, mes, cantidad });
    });
});


app.get('/api/ventas', (req, res) => {
    const sql = `SELECT * FROM ventas`;
    db.all(sql, [], (err, rows) => {
        if (err) return res.status(400).json({ error: err.message });
        res.json(rows);
    });
});


app.post('/api/chat', (req, res) => {
    const { pregunta } = req.body;
    


    
    db.all(`SELECT * FROM ventas`, [], (err, rows) => {

        const totalVentas = rows.reduce((sum, item) => sum + item.cantidad, 0);
        const respuesta = `He analizado tus datos. Tienes ${rows.length} registros y un total de ${totalVentas} ventas. ¿En qué más puedo ayudarte?`;
        
        res.json({ respuesta });
    });
});

app.listen(PORT, () => {
    console.log(`Servidor corriendo en http://localhost:${PORT}`);
});