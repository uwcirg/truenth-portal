(function() {
    var PasswordPopover = function() {
        this.__passwordReg = /^(?=.*[a-z])(?=.*[A-Z])(?=.*\d).{8,}$/;
        /*
         * get identifier string, in this case, css class, for the element that will have the popover
         */
        this.getFieldIdentifier = function() {
            return ".password-popover-field";
        };
        /*
         * get identifier string, in this case, css class, for the element that contains the popover input field
         */
        this.getWrapperContainerIdentifier = function() {
            return ".password-wrapper";
        };
        /* construct containing element if it doesn't exist
         * note containing element is needed to position the popover
         */
        this.setWrapperContainer = function() {
            var wrapperIdentifier = this.getWrapperContainerIdentifier();
            if (!$(wrapperIdentifier).length) {
                $(this.getFieldIdentifier()).wrap("<div class='"+wrapperIdentifier.replace(".","") + "'><div>");
            }
        };
        /*
         * initializing popover for the password input element
         */
        this.init = function() {
            var self = this;
            var refIdentifier = this.getFieldIdentifier();
            if (!$(refIdentifier).length) {
                return;
            }
            this.setWrapperContainer();
            $(refIdentifier).popover({"content": $("#passwordPopover .popover-content").html(), "placement": "top", "html": true, "template": $("#passwordPopover").html(), "container": this.getWrapperContainerIdentifier(), "trigger": "manual"}).click(function(e) {
                $(this).trigger("focus");
                e.stopPropagation();
            }).on("keyup", function() {
                var pwd = $(this).val(), pwdTest = self.__passwordReg.test(pwd);
                var l = $(refIdentifier).data("bs.popover").tip().find("#pwdHintList");
                if (pwdTest) {
                    //entered password match pattern, so clear error
                    $(this).closest(".form-group").find(".with-errors").text("");
                    self.setVis(pwdTest, l.find("li"));
                    setTimeout(function() {
                        $(refIdentifier).popover("hide");
                    }, 500);
                    return;
                }
                if (pwd && !$(this).data("bs.popover").tip().hasClass("in")) {
                    $(this).popover("show");
                }
                if (!pwd) {
                    l.find("li").removeClass("success-text").removeClass("fail-text");
                    return;
                }
                self.setVis(/[a-z]/.test(pwd), l.find(".lowercase-letter"));
                self.setVis(/[A-Z]/.test(pwd), l.find(".uppercase-letter"));
                self.setVis(/\d/.test(pwd), l.find(".one-number"));
                self.setVis(pwd.length >= 8, l.find(".eight-characters"));
            }).on("blur", function() {
                $(this).popover("hide");
            }).on("focus", function() {
                var pwd = $(this).val();
                if (pwd && !self.__passwordReg.test(pwd)) {
                    if (!$(this).data("bs.popover").tip().hasClass("in")) {
                        $(this).popover("show");
                    }
                } else {
                    return false;
                }
            }).on("shown.bs.popover", function () {
                $(this).trigger("keyup");
            }).on("paste", function() {
                $(this).trigger("keyup");
            });
            $("html").click(function() {
                $(refIdentifier).popover("hide");
            });
        };
        /*
         *  add success or failure css class for each popover text whose match rule is satisfied
         */
        this.setVis = function(condition, field) {
            if (condition) {
                field.removeClass("fail-text").addClass("success-text");
            } else {
                field.removeClass("success-text").addClass("fail-text");
            }
        };
    };
    $(document).ready(function() {
        (new PasswordPopover()).init();
    });
})();
