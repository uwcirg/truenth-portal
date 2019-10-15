$(document).ready(function() {
    $(".button--video").on("click", function(e) {
        e.stopPropagation();
        var vFrame = $(this).parent().find("iframe.embed-video");
        var videoSrc = vFrame.attr("src");
        vFrame.attr("src", videoSrc + "?autoplay=true");
        $(".button--video__overlay").hide();
        $(this).fadeOut();
    });
    var isSafari = !!navigator.userAgent.match(/Version\/[\d\.]+.*Safari/);
    if (isSafari) {
      $(window).resize(function() {
          if ($(".button--video").is(":visible")) {
            var src = $(".embed-video").attr("src");
            $(".embed-video").attr("src", src);
          }
      });
    }
    if ($("main").attr("data-section") === "livedexperience") {
      $("#lnReadMoreStory").hide();
    }
});
