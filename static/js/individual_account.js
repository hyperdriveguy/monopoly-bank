const do_withdraw_button = document.querySelector('#withdraw');
const do_deposit_button = document.querySelector('#deposit');
const do_transfer_button = document.querySelector('#transfer');

const withdraw_form = document.querySelector('#withdraw-form');
const deposit_form = document.querySelector('#deposit-form');
const transfer_form = document.querySelector('#transfer-form');

do_withdraw_button.addEventListener('click', () => {
    withdraw_form.classList.toggle('hidden');
    deposit_form.classList.add('hidden');
    transfer_form.classList.add('hidden');
});

do_deposit_button.addEventListener('click', () => {
    deposit_form.classList.toggle('hidden');
    withdraw_form.classList.add('hidden');
    transfer_form.classList.add('hidden');
});

do_transfer_button.addEventListener('click', () => {
    transfer_form.classList.toggle('hidden');
    withdraw_form.classList.add('hidden');
    deposit_form.classList.add('hidden');
});
