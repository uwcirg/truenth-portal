$(function() {
    var CONTENT_ELEMENT_CLASS = ".content";
    var VIDEO_PARENT_CLASS = ".video";
    var IFRAME_CLASS = ".video-frame";

    /*
     * remove loading indicator when video loaded
     */
    var checkIframeLoaded = function(iframe) {
        if (!iframe) return;
        setTimeout(function() {
            $(iframe).parent(VIDEO_PARENT_CLASS).addClass("loaded");
        }, 750);
    }

    /*
     * reset all videos to inactive
     */
    var resetAllVideo = function(el) {
        if (!el || el.length) return;
        $(IFRAME_CLASS).each(function() {
            if ($(this) === el) return true;
            var srcURL = $(this).attr("src");
             //reset all iframe autoplay setting
            if (srcURL && srcURL.indexOf("?") !== -1) {
                srcURL = srcURL.substring(0, srcURL.indexOf("?"));
                $(this).attr("src", srcURL);
            }
            $(this).parent(VIDEO_PARENT_CLASS).addClass("video-hide");
            $(this).parent(VIDEO_PARENT_CLASS).removeClass("loaded");
            $(this).closest(CONTENT_ELEMENT_CLASS).removeClass("active");
        });
    };
    /*
     * play the currently selected video
     */
    var setActiveVideo = function(el) {
        if (!el || !el.length) return;
        var contentElement =  el.closest(CONTENT_ELEMENT_CLASS);
        var videoElement = contentElement.find(IFRAME_CLASS);
        if (!videoElement.attr("src")) videoElement.attr("src", videoElement.attr("data-src"));
        var srcURL = videoElement.attr("data-src");
        //set autoplay for active video
        videoElement.attr("src", srcURL+"?autoplay=true");
        videoElement.parent(VIDEO_PARENT_CLASS).removeClass("video-hide");
        contentElement.addClass("active");
        checkIframeLoaded(videoElement);
        $("html, body").animate({
            scrollTop: videoElement.parent(VIDEO_PARENT_CLASS).offset().top - 48
        }, 750);
    };
    /*
     * stop currently playing video
     */
    var setInactiveVideo = function(el) {
        if (!el || !el.length) return;
        var contentElement =  el.closest(CONTENT_ELEMENT_CLASS);
        var videoElement = contentElement.find(IFRAME_CLASS);
        if (!videoElement.attr("src")) videoElement.attr("src", videoElement.attr("data-src"));
        var srcURL = videoElement.attr("src");
        //reset all iframe autoplay setting
        if (srcURL) {
            var videoURL = srcURL.indexOf("?") !== -1 ? srcURL.substring(0, srcURL.indexOf("?")) : srcURL;
            videoElement.attr("src", "");
            videoElement.attr("data-src", videoURL);
        }
        videoElement.parent(VIDEO_PARENT_CLASS).addClass("video-hide");
        contentElement.removeClass("active");
    };
    /*
     * play video button click event
     */
    var handleVideoLinkClick = function(el) {
        if(el.closest(CONTENT_ELEMENT_CLASS).hasClass("active")) {
            el.closest(CONTENT_ELEMENT_CLASS).removeClass("active");
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
    $(IFRAME_CLASS).each(function() {
        var attrSRC = $(this).attr("src");
        $(this).attr("data-src", attrSRC);
        $(this).attr("src", "");
    });
    $(IFRAME_CLASS).on("load", function() {
        checkIframeLoaded(this);
    });
    $(".description").on("click", function(e) {
        e.stopPropagation();
        handleVideoLinkClick($(this));
    });
});
