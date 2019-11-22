(function() {
    var SWObject = function() {
        this.requestAttempt = 0;
        this.initStartTime = new Date();
        this.initIntervalId = 0;
        //reference UUID: 1c57de26-727f-c77a-775d-5d2c27e02455, via /api/asset/uuid/1c57de26-727f-c77a-775d-5d2c27e02455
        this.contentURL = "/api/asset/tag/sexualwellbeing";
        this.init = function() {
            this.getContent();
        };
        this.getContent = function() {
            var self = this;
            this.requestAttempt++;
            $.ajax ({
                type: "GET",
                url: self.contentURL,
                timeout: 10000
            }).done(function(data) {
                self.requestAttempt = 0; //reset request attempt count
                if (!data) {
                    $("#sexualWellbeingMainContent").html("no data returned").addClass("error-message");
                    $(".pre-loader").hide();
                    return;
                }
                $("#sexualWellbeingMainContent").html(data).removeClass("error-message");
                self.initLinksEvent();
                setTimeout(function() {
                    $(".pre-loader").hide();
                }, 300);
        
            }).fail(function(xhr, status, error) {
                if (self.requestAttempt <= 3) {
                    setTimeout(function() { self.getContent();}, 3000);
                } else {
                    $("#sexualWellbeingMainContent").html(error).addClass("error-message");
                    $(".pre-loader").hide();
                    self.requestAttempt = 0;
                }
            }).always(function() {
                self.handleTimeOut();
            });
        };
        this.initLinksEvent = function() {
            var self = this;
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
            $(".content__item .title").on("click", function(e) { //mobile view
                e.stopImmediatePropagation();
                $(".content__item").removeClass("active");
                $(this).closest(".content__item").toggleClass("active");
                $("html, body").animate({ scrollTop: $(this).offset().top - $(this).outerHeight() }, 0);
            });
            $(".content__item--links li a").on("click", function(e) {
                e.stopPropagation();
            });
            $(".content__item--links li").on("click", function(e) {
                e.stopImmediatePropagation();
                var refLocation = $(this).find("a").attr("href");
                window.open(refLocation, "_blank");
            });
        };
        this.handleTimeOut = function() {
            this.initIntervalId = setInterval(function() { //after ajax call, check if content is actually returned
                var initEndTime = new Date();
                var elapsedTime = initEndTime - this.initStartTime;
                elapsedTime /= 1000;
                if (elapsedTime >= 35) { //35 second elapsed and no content returned
                    clearInterval(this.initIntervalId);
                    if (!$("#sexualWellbeingMainContent").text()) {
                        $("#sexualWellbeingMainContent").html("Timed out retrieving content.").addClass("error-message");
                    }
                    $(".pre-loader").hide();
                }
            }.bind(this), 30);
        };
    };
    $(function() {
        (new SWObject()).init();
    });
})();
