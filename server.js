const express = require('express');
const Gamedig = require('gamedig');
const cors = require('cors');

const app = express();
const port = 3000;

app.use(cors());

app.get('/players', async (req, res) => {
    try {
        const state = await Gamedig.query({
            type: 'spaceengineers',
            host: '192.169.93.178', 
            port: 27019             
        });

        if (state && state.players) {
            res.json(state.players);
        } else {
            res.status(500).json({ error: 'Players data not found in response' });
        }
    } catch (error) {
        console.error('Error fetching server data:', error);
        res.status(500).json({ error: `Failed to fetch server data: ${error.message}` });
    }
});

app.listen(port, () => {
    console.log(`Server running on port ${port}`);
});
