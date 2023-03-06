// Forms or other elements that are sensitive to refreshes when unhidden.
const update_sensitive = [document.querySelector('#make-new-acc'), document.querySelector('#transfer-form')];

// Don't force refresh if accounts change.
// If the intention is to create or modify an account,
// preserving the form is more important.
function keepFormsAlive() {
    return update_sensitive.some(element => {
        if (element == undefined) {
            return false;
        }
        // Check if the sensitive element is hidden
        if (!element.classList.contains('hidden')) {
            if (!confirm('Account data has been updated, but you\'re in the middle of creating an account. Refresh the page anyway?')) {
                return true;
            }
        }
        return false;
    });
}

const update_event = new EventSource("/bruh");

window.addEventListener('load', () => {
    update_event.onmessage = function(req) {
        res = JSON.parse(req.data)
        if (res['sync']) {
            if (keepFormsAlive()) {
                return;
            }
            window.location=window.location;
        }
        console.log(req.data);
    }; 
    update_event.addEventListener('error', function(event) {
        console.error("Failed to connect to event stream for auto update.");
    }, false);
});

// The event must be unloaded from the page manually to prevent breakage.
// https://bugzilla.mozilla.org/show_bug.cgi?id=833462
window.addEventListener('beforeunload', () => {
	update_event.close();
});
