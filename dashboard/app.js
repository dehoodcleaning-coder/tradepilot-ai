// Configurações do Supabase & Binance Ticker
const SUPABASE_URL = "https://skrnjqpoxwjuaffoctsp.supabase.co";
const SUPABASE_KEY = "sb_publishable_mNTPWQkt-KxFUdGn7qZ0VQ_jCGCh76a";

const SYMBOLS = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'BNB/USDT', 'XRP/USDT', 'ADA/USDT'];

// Dados em Memória
let allSetups = [];
let assetStatus = {
    'BTC/USDT': { price: 64620.50, poiLow: 64580.00, poiHigh: 64650.00, sweep: true, fvg: true, choch: true, direction: 'BUY', score: 83 },
    'ETH/USDT': { price: 1912.20, poiLow: 1908.00, poiHigh: 1914.00, sweep: true, fvg: true, choch: true, direction: 'SELL', score: 78 },
    'SOL/USDT': { price: 73.50, poiLow: 73.20, poiHigh: 73.60, sweep: true, fvg: true, choch: true, direction: 'BUY', score: 85 },
    'BNB/USDT': { price: 594.30, poiLow: 593.00, poiHigh: 595.00, sweep: false, fvg: true, choch: false, direction: 'BUY', score: 68 },
    'XRP/USDT': { price: 1.0510, poiLow: 1.0500, poiHigh: 1.0520, sweep: true, fvg: true, choch: true, direction: 'SELL', score: 80 },
    'ADA/USDT': { price: 0.4250, poiLow: 0.4220, poiHigh: 0.4260, sweep: false, fvg: true, choch: true, direction: 'BUY', score: 72 }
};

// Inicialização da Aplicação
document.addEventListener('DOMContentLoaded', () => {
    renderAssetGrid();
    fetchLiveSetups();
    setupFilterPills();

    // Polling a cada 5 segundos
    setInterval(fetchLiveSetups, 5000);
    setInterval(updatePricesSimulation, 3000);
});

// Busca Setups do Supabase Cloud REST API
async function fetchLiveSetups() {
    try {
        const res = await fetch(`${SUPABASE_URL}/rest/v1/tradepilot_setups?select=*&order=created_at.desc&limit=30`, {
            headers: {
                "apikey": SUPABASE_KEY,
                "Authorization": `Bearer ${SUPABASE_KEY}`
            }
        });
        if (res.ok) {
            const data = await res.json();
            if (data && data.length > 0) {
                allSetups = data;
                renderSignalsFeed(allSetups);
                updateKPIs(allSetups);
            }
        }
    } catch (e) {
        console.warn("Erro ao consultar Supabase REST:", e);
    }
}

// Renderiza Grid de 6 Ativos (Varredura 24/7)
function renderAssetGrid() {
    const grid = document.getElementById('assetScannerGrid');
    grid.innerHTML = '';

    SYMBOLS.forEach(sym => {
        const info = assetStatus[sym];
        const card = document.createElement('div');
        card.className = 'asset-card';
        card.onclick = () => selectAssetForVisualizer(sym, info);

        const dirColor = info.direction === 'BUY' ? '#00e676' : '#ff1744';

        card.innerHTML = `
            <div class="asset-card-header">
                <span class="asset-name">${sym}</span>
                <span class="asset-price" style="color: ${dirColor};">$${info.price.toFixed(sym.includes('XRP') || sym.includes('ADA') ? 4 : 2)}</span>
            </div>
            <div class="asset-poi-box">
                <div class="poi-label">Faixa POI (5m):</div>
                <div class="poi-range">$${info.poiLow.toFixed(2)} - $${info.poiHigh.toFixed(2)}</div>
            </div>
            <div class="tag-list">
                ${info.sweep ? '<span class="tag sweep">✓ SWEEP PIVÔ</span>' : '<span class="tag" style="background:rgba(255,255,255,0.05)">SEM SWEEP</span>'}
                ${info.fvg ? '<span class="tag fvg">✓ FVG</span>' : ''}
                ${info.choch ? '<span class="tag choch">✓ CHoCH 1m</span>' : ''}
            </div>
        `;
        grid.appendChild(card);
    });
}

// Renderiza Feed de Sinais Encadeados
function renderSignalsFeed(setups) {
    const list = document.getElementById('signalsList');
    list.innerHTML = '';

    setups.forEach(s => {
        const item = document.createElement('div');
        item.className = 'signal-item';
        item.onclick = () => selectSetupForVisualizer(s);

        const isOfficial = s.alert_type === 'ENTRY_ELIGIBLE' || s.total_score >= 80;
        const badgeClass = isOfficial ? 'badge-official' : 'badge-pre';
        const badgeText = isOfficial ? '🚀 ALERTA OFICIAL (ENTRADA)' : '👀 PRÓ-ALERTA (EM TESTE)';
        const dirColor = s.direction === 'BUY' ? '#00e676' : '#ff1744';

        item.innerHTML = `
            <div class="signal-item-header">
                <span class="signal-type-badge ${badgeClass}">${badgeText}</span>
                <span class="signal-score" style="color: ${dirColor}">${s.total_score}/100 PTS</span>
            </div>
            <div style="display: flex; justify-content: space-between; font-weight: 600; font-size: 0.95rem; margin-bottom: 4px;">
                <span>${s.symbol}</span>
                <span style="color: ${dirColor}">${s.direction} @ $${s.entry_price}</span>
            </div>
            <div style="font-size: 0.75rem; color: #848e9c;">
                ${s.setup_scenario || 'Cenário SMC Peixe Grande'}
            </div>
        `;
        list.appendChild(item);
    });
}

// Seleciona um Setup para o Visualizador Interativo
function selectSetupForVisualizer(s) {
    document.getElementById('selectedSymbolTag').innerText = `${s.symbol} (${s.direction})`;
    document.getElementById('setupScenarioTitle').innerText = s.setup_scenario || 'CENÁRIO 1: Reversão por Captura de Liquidez';
    document.getElementById('valEntry').innerText = `$${s.entry_price}`;
    document.getElementById('valStop').innerText = `$${s.stop_loss}`;
    document.getElementById('valTp1').innerText = `$${s.take_profit_1}`;
    document.getElementById('valTp2').innerText = `$${s.take_profit_2}`;
}

function selectAssetForVisualizer(sym, info) {
    document.getElementById('selectedSymbolTag').innerText = `${sym} (${info.direction})`;
    document.getElementById('valEntry').innerText = `$${info.price.toFixed(2)}`;
    document.getElementById('valStop').innerText = `$${(info.price * 0.995).toFixed(2)}`;
    document.getElementById('valTp1').innerText = `$${(info.price * 1.01).toFixed(2)}`;
    document.getElementById('valTp2').innerText = `$${(info.price * 1.025).toFixed(2)}`;
}

// Atualiza KPIs Globais
function updateKPIs(setups) {
    document.getElementById('kpiTotalSetups').innerText = setups.length;
}

// Filtros por Categoria
function setupFilterPills() {
    const pills = document.querySelectorAll('.pill');
    pills.forEach(p => {
        p.addEventListener('click', () => {
            pills.forEach(x => x.classList.remove('active'));
            p.classList.add('active');

            const filter = p.getAttribute('data-filter');
            if (filter === 'official') {
                renderSignalsFeed(allSetups.filter(x => x.total_score >= 80));
            } else if (filter === 'pre') {
                renderSignalsFeed(allSetups.filter(x => x.total_score < 80));
            } else {
                renderSignalsFeed(allSetups);
            }
        });
    });
}

// Simulação de Oscilação de Preços ao Vivo
function updatePricesSimulation() {
    SYMBOLS.forEach(sym => {
        const delta = (Math.random() - 0.5) * (assetStatus[sym].price * 0.0005);
        assetStatus[sym].price += delta;
    });
    renderAssetGrid();
    document.getElementById('lastSyncTime').innerText = `Sincronizado: ${new Date().toLocaleTimeString('pt-BR')}`;
}
