(function() {
    var SWObject = function() {
        this.requestAttempt = 0;
        this.initStartTime = new Date();
        this.initIntervalId = 0;
         //TODO, hardcode uuid here, will change once the API has been modified to accept tag
        this.contentURL = "/api/asset/uuid/1c57de26-727f-c77a-775d-5d2c27e02455";
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
                $("#sexualWellbeingMainContent").html(data).removeClass("error-message");
                self.initLinksEvent();
                $(".pre-loader").hide();
        
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
        this.reportDownload = function(referenceURL) {
            if (!referenceURL) {
                return;
            }
            if (typeof _paq !== "undefined") {
                _paq.push(['trackLink', referenceURL , 'download']);
            }
        }
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
            $(".content__item .title").on("click", function() {
                $(".content__item").removeClass("active");
                $(this).closest(".content__item").toggleClass("active");
            });
            $(".content__item--links li a").on("click", function(e) {
                e.stopPropagation();
                //self.reportDownload($(this).attr("href"));
            });
            $(".content__item--links li").on("click", function(e) {
                e.stopImmediatePropagation();
                var refLocation = $(this).find("a").attr("href");
                //self.reportDownload(refLocation);
                setTimeout(function() {
                    window.open(refLocation, '_blank');
                }, 0);

               
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
