$(".button-container").each(function() {
    $(this).prepend('<div class="loading-message-indicator"><i class="fa fa-spinner fa-spin fa-2x"></i></div>');
});
$(".btn-tnth-primary").on("click", function() {
    var link = $(this).attr("href");
    if (hasValue(link)) {
        event.preventDefault();
        $(this).hide();
        $(this).prev(".loading-message-indicator").show();
        setTimeout(function() {
            window.location=link;
        }, 300);
    };
});
$(document).on("ready", function() {
    $("#mainDiv").addClass("portal");
    $("#portalScrollArrow").on("click", function() {
        var t = $(".portal-main").offset().top;
        if (parseInt(t) >= 90) {
            $('html, body').animate({
                scrollTop: t - 90
            }, 1000);
        };
    });
});