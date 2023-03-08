function make_margin() {
    let target_margin = document.querySelector('.side-bar').offsetWidth;
    // Set left margin of the main section to the width of the sidebar
    document.querySelector('main').style.margin = `0 0 0 ${target_margin + 10}px`;
}

make_margin();

window.addEventListener("load", make_margin);
window.addEventListener("resize", make_margin);
