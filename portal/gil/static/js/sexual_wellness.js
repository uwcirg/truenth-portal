(function() {
    var requestAttempt = 0;
    var getContent = function() {
        $.ajax ({
            type: "GET",
            //TODO, hardcode uuid here, will change once the API has been modified to accept tag
            url: "/api/asset/uuid/1c57de26-727f-c77a-775d-5d2c27e02455",
            timeout: 10000
        }).done(function(data) {
            requestAttempt++;
            $("#sexualWellbeingMainContent").html(data).removeClass("error-message");
            initLinksEvent();
            $(".pre-loader").hide();
    
        }).fail(function(xhr, status, error) {
            if (requestAttempt <= 3) {
                setTimeout(function() { getContent;}, 3000);
            } else {
                $("#sexualWellbeingMainContent").html(error).addClass("error-message");
                $(".pre-loader").hide();
                requestAttempt = 0;
            }
        });
    };
    var initLinksEvent = function() {
        $(".item__link").on("click", function() {
            $(".item__link").removeClass("active");
            $(this).addClass("active");
            $(".content__item").removeClass("active");
            $(".content__item[data-group="+ $(this).attr("data-group") + "]").addClass("active");
        });
        var activeItemLinkGroup = $(".item__link.active").attr("data-group");
        if (activeItemLinkGroup) {
            $(".content__item[data-group="+activeItemLinkGroup+"]").addClass("active");
        }
        $(".content__item .title").on("click", function() {
            $(".content__item").removeClass("active");
            $(this).closest(".content__item").toggleClass("active");
        });
        $(".content__item--links li").on("click", function() {
            $(this).find("a")[0].click();
        });
    };
    var initStartTime = new Date();
    var handleTimeOut = function() {
        var initIntervalId = setInterval(function() { //wait for ajax calls to finish
            var initEndTime = new Date();
            var elapsedTime = initEndTime - initStartTime;
            elapsedTime /= 1000;
            if (elapsedTime >= 35) { //35 second elapsed and no content returned
                clearInterval(initIntervalId);
                if (!$("#sexualWellbeingMainContent").text()) {
                    $("#sexualWellbeingMainContent").html("Timed out retrieving content.").addClass("error-message");
                }
                $(".pre-loader").hide();
            }
        }, 30);
    };
    $(function() {
        getContent();
        handleTimeOut();
    });
})();

