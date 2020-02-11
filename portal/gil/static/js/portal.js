$(document).ready(function() {
    $("body").attr("class", "page-home");
    $("aside").hide();
    $(".side-nav-items__item--home").hide();
    var hc = $(".home--item-container");
    if (hc.length > 0) {
        $("#portalScrollArrow").on("click", function() {
            var t = $("section.home--items-wrapper").offset().top;
            if (parseInt(t) >= 90) {
                $("html, body").animate({
                    scrollTop: t - 90
                }, 1000);
            }
        });
    }
    if (hc.length === 1) {
        hc.removeClass("home--item-container").addClass("home--item-container-full");
    }
});
