document.addEventListener('DOMContentLoaded', function() {
    console.log('Investments script loaded');

    // Handle Buy/Sell Forms
    document.querySelectorAll('.buy-form, .sell-form').forEach(form => {
        // Remove any existing event listeners by cloning and replacing the node
        // This ensures we don't have duplicate listeners if the script runs multiple times
        const newForm = form.cloneNode(true);
        form.parentNode.replaceChild(newForm, form);
        
        newForm.addEventListener('submit', async (e) => {
            e.preventDefault(); // CRITICAL: Stop normal form submission
            console.log('Form submission intercepted');

            const actionInput = newForm.querySelector('input[name="action"]');
            const numSharesInput = newForm.querySelector('input[name="num_shares"]');
            
            const action = actionInput ? actionInput.value : null;
            const stockName = newForm.getAttribute('data-stock-name');
            const numShares = numSharesInput ? parseInt(numSharesInput.value) : 0;

            console.log('Trade details:', { action, stockName, numShares });

            if (!stockName || !action || !numShares) {
                alert('Error: Missing trade information');
                return;
            }

            if (isNaN(numShares) || numShares <= 0) {
                alert('Error: Please enter a valid number of shares');
                return;
            }

            const submitBtn = newForm.querySelector('button[type="submit"]');
            if (submitBtn) submitBtn.disabled = true; // Prevent double submission

            try {
                console.log('Sending request to /investments/api...');
                const response = await fetch('/investments/api', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Accept': 'application/json'
                    },
                    body: JSON.stringify({
                        action: action,
                        stock_name: stockName,
                        num_shares: numShares
                    })
                });

                console.log('Response status:', response.status);
                
                const contentType = response.headers.get("content-type");
                if (contentType && contentType.indexOf("application/json") !== -1) {
                    const data = await response.json();
                    console.log('Response data:', data);

                    if (data.success) {
                        alert(data.message);
                        location.reload();
                    } else {
                        alert('Error: ' + data.message);
                        if (submitBtn) submitBtn.disabled = false;
                    }
                } else {
                    console.error('Received non-JSON response');
                    const text = await response.text();
                    console.error('Response text:', text);
                    alert('Server error: Received invalid response format');
                    if (submitBtn) submitBtn.disabled = false;
                }

            } catch (error) {
                console.error('Fetch error:', error);
                alert('Failed to process trade: ' + error.message);
                if (submitBtn) submitBtn.disabled = false;
            }
        });
    });

    // Chart Rendering Logic
    document.querySelectorAll('.price-history').forEach(canvas => {
        try {
            const historyData = canvas.dataset.history;
            if (!historyData) return;

            const history = JSON.parse(historyData);
            if (!Array.isArray(history) || history.length === 0) return;
            
            const ctx = canvas.getContext('2d');
            const width = canvas.offsetWidth;
            const height = canvas.offsetHeight;
            
            // Handle high DPI displays if needed, but keeping it simple for now
            canvas.width = width;
            canvas.height = height;
            
            const minPrice = Math.min(...history);
            const maxPrice = Math.max(...history);
            const range = maxPrice - minPrice || 1;
            const padding = 5;
            
            // Draw background
            ctx.fillStyle = '#f8f9fa';
            ctx.fillRect(0, 0, width, height);
            
            // Draw line chart
            ctx.strokeStyle = '#667eea';
            ctx.lineWidth = 2;
            ctx.beginPath();
            
            history.forEach((price, index) => {
                const x = padding + (index / (history.length - 1 || 1)) * (width - 2 * padding);
                const y = height - padding - ((price - minPrice) / range) * (height - 2 * padding);
                
                if (index === 0) {
                    ctx.moveTo(x, y);
                } else {
                    ctx.lineTo(x, y);
                }
            });
            ctx.stroke();
            
            // Draw fill
            ctx.lineTo(width - padding, height - padding);
            ctx.lineTo(padding, height - padding);
            ctx.closePath();
            ctx.fillStyle = 'rgba(102, 126, 234, 0.1)';
            ctx.fill();
        } catch (e) {
            console.error('Error rendering chart:', e);
        }
    });
});
