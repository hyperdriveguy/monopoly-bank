const new_account_button = document.querySelector('#new-account');
const new_account_form = document.querySelector('#make-new-acc');

const del_account_button = document.querySelector('#del-account');
const individual_account_del_buttons = document.querySelectorAll('.indv-acc-del');
const account_cards = document.querySelectorAll('a.card-stylize');

const refresh_button = document.querySelector('#refresh');

// Dirty hack to post to server
function post(path, params, method='post') {
    const form = document.createElement('form');
    form.method = method;
    form.action = path;
  
    for (const key in params) {
      if (params.hasOwnProperty(key)) {
        const hiddenField = document.createElement('input');
        hiddenField.type = 'hidden';
        hiddenField.name = key;
        hiddenField.value = params[key];
  
        form.appendChild(hiddenField);
      }
    }
  
    document.body.appendChild(form);
    form.submit();
  }  

if (new_account_button != null) {
    new_account_button.addEventListener('click', () => {
        new_account_form.classList.toggle('hidden');
        individual_account_del_buttons.forEach(node => {
            node.classList.add("hidden");
        });
        account_cards.forEach(node => {
            node.classList.add("clickable");
        })
    });
}

if (del_account_button != null) {
    del_account_button.addEventListener('click', () => {
        new_account_form.classList.add('hidden');
        individual_account_del_buttons.forEach(node => {
            node.classList.toggle("hidden");
        });
        account_cards.forEach(node => {
            node.classList.toggle("clickable");
        })
    });
}

individual_account_del_buttons.forEach(node => {
    node.addEventListener('click', () => {
        if (confirm(`Delete account with ID "${node.attributes.account.value}"?`)) {
            post("", {"del-acc-id": node.attributes.account.value});
        }
    });
});

refresh_button.addEventListener('click', () => {
    window.location=window.location;
})
