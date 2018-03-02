var ResourcesTool = function() {
    this.init = function() {
        $(".tab-label").on("click", function() {
            $(this).toggleClass("active");
        });
        $(".tab-label").trigger("click");
        this.handlePrint();
    };
    this.handlePrint = function() {
        var self = this;
        $("#homeFooter").addClass("hidden-print");
        self.startTime = new Date();
        self.tVar = setInterval(function(){
                    self.endTime = new Date();
                    var elapsedTime = self.endTime - self.startTime;
                    elapsedTime /= 1000;
                    if (!$("#tnthNavWrapper").hasClass("no-fouc") || elapsedTime >= 3) {
                        $("#tnthNavWrapper, .watermark").each(function() {
                            $(this).addClass("hidden-print");
                        });
                        clearInterval(self.tVar);
                    }
                }, 1000);
        $(".work-instruction-printicon").on("click", function(e) {
            e.stopPropagation();
            window.print();
        });
    };
}

$(function() {
    (new ResourcesTool()).init();
});