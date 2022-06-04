window.addEventListener('load', () => {
    const source = new EventSource("/bruh");
    source.onmessage = function(req) {
        res = JSON.parse(req.data)
        if (res['sync']) {
            // Don't force refresh if accounts change.
            // If the intention is to create a new account,
            // preserving the form is more important.
            if (new_account_form != undefined && !new_account_form.classList.contains('hidden')) {
                if (!confirm('Account data has been updated, but you\'re in the middle of creating an account. Refresh the page anyway?')) {
                    return;
                }
            }
            window.location=window.location;
        }
        console.log(req.data);
    }; 
    source.addEventListener('error', function(event) {
        console.log("Failed to connect to event stream for auto update.");
    }, false);
});
