// Forms or other elements that are sensitive to refreshes when unhidden.
const update_sensitive = [document.querySelector('#make-new-acc'), document.querySelector('#transfer-form')];
let initial_event_done = false;

function isPostBack() {
    return document.referrer.indexOf(document.location.href) > -1;
}

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

window.addEventListener('load', () => {
    if (!isPostBack()) {
        initial_event_done = true;
    }
    // Wait 100ms for potential event
    setTimeout(() => {initial_event_done = true;}, 100);
    const source = new EventSource("/bruh");
    source.onmessage = function(req) {
        res = JSON.parse(req.data)
        if (res['sync']) {
            if (!initial_event_done) {
                initial_event_done = true;
                return;
            }
            if (keepFormsAlive()) {
                return;
            }
            window.location=window.location;
        }
        console.log(req.data);
    }; 
    source.addEventListener('error', function(event) {
        console.log("Failed to connect to event stream for auto update.");
    }, false);
});
