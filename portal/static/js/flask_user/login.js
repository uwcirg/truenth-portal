$("document").ready(function() { /*global $ */
    if (!$(".landing").length) {
        $("#mainNav").removeClass("hidden");
    }
    // check if a Remember Me cookie has been stored, 
    // and assigned cookie value to input field whose value will be submitted to backend
    initRememberMeInputField();
});

