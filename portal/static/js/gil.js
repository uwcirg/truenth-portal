(function e(t,n,r){function s(o,u){if(!n[o]){if(!t[o]){var a=typeof require=="function"&&require;if(!u&&a)return a(o,!0);if(i)return i(o,!0);throw new Error("Cannot find module '"+o+"'")}var f=n[o]={exports:{}};t[o][0].call(f.exports,function(e){var n=t[o][1][e];return s(n?n:e)},f,f.exports,e,t,n,r)}return n[o].exports}var i=typeof require=="function"&&require;for(var o=0;o<r.length;o++)s(r[o]);return s})({1:[function(require,module,exports){
module.exports = {
  fx: {
    easing: 'easeOutExpo',
    speed: {
      slow: 1500,
      mid: 1000,
      fast: 1000
    }
  }
};


},{}],2:[function(require,module,exports){
var admin, global, navToggle, upperBanner, video, windowResize, windowScroll;

upperBanner = require('./modules/upper-banner');

windowScroll = require('./modules/window-scroll');

windowResize = require('./modules/window-resize');

navToggle = require('./modules/nav-toggle');

global = require('./modules/global');

admin = require('./modules/admin');

video = require('./modules/video');

$(function() {
  if (window.app == null) {
    window.app = {};
  }
  window.app.global = new global();
  window.app.upperBanner = new upperBanner();
  window.app.windowScroll = new windowScroll();
  window.app.windowResize = new windowResize();
  window.app.navToggle = new navToggle();
  window.app.admin = new admin();
  return window.app.video = new video();
});


},{"./modules/admin":3,"./modules/global":4,"./modules/nav-toggle":5,"./modules/upper-banner":6,"./modules/video":7,"./modules/window-resize":8,"./modules/window-scroll":9}],3:[function(require,module,exports){
var Admin, loggedInAdminClass, loggedInClass, upperBannerClosedClass;

loggedInAdminClass = 'is-showing-logged-in';

loggedInClass = 'is-logged-in';

upperBannerClosedClass = 'is-upper-banner-closed';

module.exports = Admin = (function() {
  function Admin() {
    this.build();
  }

  Admin.prototype.build = function() {
    return $('.js-mock-submit').on('submit', function(e) {
      e.preventDefault();
      return $(this).addClass('is-submitted');
    });
  };

  return Admin;

})();


},{}],4:[function(require,module,exports){
var Global, config;

config = require('../config');

module.exports = Global = (function() {
  function Global() {
    this.addFX();
    this.addPlugins();
    this.bindEvents();
  }

  Global.prototype.addFX = function() {
    return $.extend($.easing, window.easing);
  };

  Global.prototype.addPlugins = function() {
    $('.modal').on('show.bs.modal', function(e) {
      return $(this).addClass('is-modal-active');
    });
    return $('.modal').on('hide.bs.modal', function(e) {
      var $this;
      $this = $(this);
      return setTimeout(function() {
        return $this.removeClass('is-modal-active');
      }, 200);
    });
  };

  Global.prototype.bindEvents = function() {
    return $('.js-scroll-down').on('click', function(e) {
      var $target, position;
      e.preventDefault();
      $target = $($(this).attr('data-target'));
      position = $target.offset().top + $target.outerHeight() - 92;
      return $('html,body').animate({
        scrollTop: position
      }, config.fx.speed.mid, config.fx.easing);
    });
  };

  return Global;

})();


},{"../config":1}],5:[function(require,module,exports){
var NavToggle, navExpandedClass;

navExpandedClass = 'is-nav-expanded';

module.exports = NavToggle = (function() {
  function NavToggle() {
    this.build();
  }

  NavToggle.prototype.build = function() {
    $('.js-nav-menu-toggle').on('click', function(e) {
      e.preventDefault();
      return $('html').toggleClass(navExpandedClass, !$('html').hasClass(navExpandedClass));
    });
    $("figure.nav-overlay, .js-close-nav").on('click', function(e) {
      if ($('html').hasClass(navExpandedClass)) {
        return $('html').removeClass(navExpandedClass);
      }
    });
    $('.side-nav a').not('[data-toggle=modal]').on('click touchend', function(e) {
      var href;
      e.preventDefault();
      href = $(this).attr('href');
      $('html').removeClass(navExpandedClass);
      return setTimeout(function() {
        return window.location = href;
      }, 1000);
    });
    return $('.side-nav a[data-toggle=modal]').on('click touchend', function(e) {
      var target;
      e.preventDefault();
      target = $(this).attr('data-target');
      $('html').removeClass(navExpandedClass);
      return setTimeout(function() {
        return $(target).modal('show');
      }, 500);
    });
  };

  return NavToggle;

})();


},{}],6:[function(require,module,exports){
var UpperBanner;

module.exports = UpperBanner = (function() {
  function UpperBanner() {
    this.build();
  }

  UpperBanner.prototype.build = function() {
    return $('.js-close-upper-banner').on('click touchstart', function(e) {
      e.preventDefault();
      return $('html').addClass('is-upper-banner-closed');
    });
  };

  return UpperBanner;

})();


},{}],7:[function(require,module,exports){
var Video, navExpandedClass;

navExpandedClass = 'is-nav-expanded';

module.exports = Video = (function() {
  function Video() {
    this.build();
  }

  Video.prototype.build = function() {
    $('.js-video-toggle a').on('click', function(e) {
      return e.preventDefault();
    });
    return $('.js-video-toggle').on('click', function(e) {
      var $div, src;
      e.preventDefault();
      $('html').addClass('is-video-active');
      $div = $(this);
      src = $div.data('iframe-src');
      return $div.append("<iframe src='" + src + "' allowfullscreen frameborder='0' />").addClass('is-js-video-active');
    });
  };

  return Video;

})();


},{}],8:[function(require,module,exports){
var Resize;

module.exports = Resize = (function() {
  function Resize() {
    var $intro;
    $intro = $('.intro');
    $intro.imagesLoaded(function() {
      return $(window).on('resize.setElements', _.debounce(function(e) {
        var imgHeight;
        if ($(window).width() <= 767) {
          imgHeight = $intro.find('img.intro__img--mobile').height();
        } else {
          imgHeight = $intro.find('img.intro__img--desktop').height();
        }
        return $intro.css('height', imgHeight);
      }, 50)).trigger('resize.setElements');
    });
  }

  return Resize;

})();


},{}],9:[function(require,module,exports){
var WindowScroll;

module.exports = WindowScroll = (function() {
  function WindowScroll() {
    this.bindScroll();
  }

  WindowScroll.prototype.bindScroll = function() {
    var checkScroll;
    checkScroll = _.debounce(function() {
      var offset;
      if ($('.upper-banner').outerHeight() > 0) {
        offset = $('.upper-banner').outerHeight();
      } else {
        offset = 0;
      }
      if ($(window).scrollTop() <= offset) {
        return $('html').removeClass('is-scrolled');
      } else {
        return $('html').addClass('is-scrolled');
      }
    }, 0);
    return $(window).on('scroll.checkScroll', checkScroll).trigger('scroll.checkScroll');
  };

  return WindowScroll;

})();


},{}]},{},[2])