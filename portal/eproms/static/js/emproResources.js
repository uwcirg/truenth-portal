$(function() {

    /*
     * remove loading indicator when video loaded
     */
    var checkIframeLoaded = function(iframe) {
        if (!iframe) return;
        setTimeout(function() {
            $(iframe).parent(".video").addClass("loaded");
        }, 750);
    }

    /*
     * reset all videos to inactive
     */
    var resetAllVideo = function(el) {
        if (!el || el.length) return;
        $(".video-frame").each(function() {
            if ($(this) === el) return true;
            var srcURL = $(this).attr("src");
             //reset all iframe autoplay setting
            if (srcURL && srcURL.indexOf("?") !== -1) {
                srcURL = srcURL.substring(0, srcURL.indexOf("?"));
                $(this).attr("src", srcURL);
            }
            $(this).parent(".video").addClass("video-hide");
            $(this).parent(".video").removeClass("loaded");
            $(this).closest(".content").removeClass("active");
        });
    };
    /*
     * play the currently selected video
     */
    var setActiveVideo = function(el) {
        if (!el || !el.length) return;
        var contentElement =  el.closest(".content");
        var videoElement = contentElement.find(".video-frame");
        if (!videoElement.attr("src")) videoElement.attr("src", videoElement.attr("data-src"));
        var srcURL = videoElement.attr("data-src");
        //set autoplay for active video
        videoElement.attr("src", srcURL+"?autoplay=true");
        videoElement.parent(".video").removeClass("video-hide");
        contentElement.addClass("active");
        checkIframeLoaded(videoElement);
        $("html, body").animate({
            scrollTop: videoElement.parent(".video").offset().top - 48
        }, 750);
    };
    /*
     * stop currently playing video
     */
    var setInactiveVideo = function(el) {
        if (!el || !el.length) return;
        var contentElement =  el.closest(".content");
        var videoElement = contentElement.find(".video-frame");
        if (!videoElement.attr("src")) videoElement.attr("src", videoElement.attr("data-src"));
        var srcURL = videoElement.attr("src");
        //reset all iframe autoplay setting
        if (srcURL) {
            var videoURL = srcURL.indexOf("?") !== -1 ? srcURL.substring(0, srcURL.indexOf("?")) : srcURL;
            videoElement.attr("src", "");
            videoElement.attr("data-src", videoURL);
        }
        videoElement.parent(".video").addClass("video-hide");
        contentElement.removeClass("active");
    };
    /*
     * play video button click event
     */
    var handleVideoLinkClick = function(el) {
        if(el.closest(".content").hasClass("active")) {
            el.closest(".content").removeClass("active");
            setInactiveVideo(el);
            return;
        }
        resetAllVideo(el);
        setActiveVideo(el);
    };
    /*
     * prevent all videos from loaded at runtime
     * load video only on demand
     */
    $(".video-frame").each(function() {
        var attrSRC = $(this).attr("src");
        $(this).attr("data-src", attrSRC);
        $(this).attr("src", "");
    });
    $(".video-frame").on("load", function() {
        checkIframeLoaded(this);
    });
    $(".description").on("click", function(e) {
        e.stopPropagation();
        handleVideoLinkClick($(this));
    });
});
