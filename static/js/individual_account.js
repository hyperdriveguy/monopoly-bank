const do_withdraw_button = document.querySelector('#withdraw');
const do_deposit_button = document.querySelector('#deposit');

const withdraw_form = document.querySelector('#withdraw-form');
const deposit_form = document.querySelector('#deposit-form');

do_withdraw_button.addEventListener('click', () => {
    withdraw_form.classList.toggle('hidden');
    deposit_form.classList.add('hidden');
});

do_deposit_button.addEventListener('click', () => {
    deposit_form.classList.toggle('hidden');
    withdraw_form.classList.add('hidden');
});
