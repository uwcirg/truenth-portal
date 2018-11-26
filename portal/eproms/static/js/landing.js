$(document).ready(function() {
    resetBrowserBackHistory(); /* global resetBrowserBackHistory */
    DELAY_LOADING = true; /* global DELAY_LOADING */
    setTimeout(function() {
        DELAY_LOADING = false;
        showMain(); /* global showMain */
        hideLoader(true); /* global hideLoader */
    }, 150);
    if (typeof sessionStorage !== "undefined") {
        sessionStorage.clear();
    }
});

