document.addEventListener('DOMContentLoaded', () => {
    const costInput = document.getElementById('costInput');
    const saleInput = document.getElementById('saleInput');
    const profitResult = document.getElementById('profitResult');
    const roiResult = document.getElementById('roiResult');
    const breakevenResult = document.getElementById('breakevenResult');

    function calculateProfit() {
        const cost = parseFloat(costInput.value) || 0;
        const sale = parseFloat(saleInput.value) || 0;

        const profit = sale - cost;
        const roi = cost === 0 ? 0 : (profit / cost) * 100;
        const breakeven = sale === 0 ? 0 : cost / sale;

        profitResult.textContent = profit.toFixed(2);
        roiResult.textContent = `${roi.toFixed(2)}%`;
        breakevenResult.textContent = breakeven.toFixed(2);

        // Renklendirme
        profitResult.classList.remove('positive', 'negative');
        roiResult.classList.remove('positive', 'negative');

        if (profit > 0) {
            profitResult.classList.add('positive');
        } else if (profit < 0) {
            profitResult.classList.add('negative');
        }

        if (roi > 0) {
            roiResult.classList.add('positive');
        } else if (roi < 0) {
            roiResult.classList.add('negative');
        }
    }

    costInput.addEventListener('input', calculateProfit);
    saleInput.addEventListener('input', calculateProfit);

    // Initial calculation on load
    calculateProfit();

    // Listen for messages from sidepanel.js to set sale price
    chrome.runtime.onMessage.addListener((msg) => {
        if (msg.action === 'setSalePrice') {
            saleInput.value = msg.price.toFixed(2);
            calculateProfit();
        }
    });
});
