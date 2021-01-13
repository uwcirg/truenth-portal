export function getWrapperJS (el) {
    if (!el) return;
    let jsSet = document.querySelectorAll(`${el} script`); 
    jsSet.forEach(item => {
        var d=document, g=d.createElement("script"), b=d.getElementsByTagName("body")[0];
        if (!item.getAttribute("src")) {
            g.innerHTML = item.innerHTML;
            b.appendChild(g);
            return true;
        }
        let props = {
            type: "text/javascript",
            async: true,
            defer: true,
            src: item.getAttribute("src")
        };
        for (const [key, value] of Object.entries(props)) {
            g[key] = value;
        }
        b.appendChild(g);
    });
};
export function sendRequest (url, params) {

    params = params || {};
    // Return a new promise.
    return new Promise(function(resolve, reject) {
      // Do the usual XHR stuff
      var req = new XMLHttpRequest();
      req.open('GET', url);
      req.onload = function() {
        // This is called even on 404 etc
        // so check the status
        if (req.status == 200) {
          // Resolve the promise with the response text
          resolve(req.response);
        }
        else {
          // Otherwise reject with the status text
          // reject with error, which will hopefully be a meaningful message
          reject(req);
        }
      };
  
      // Handle network errors
      req.onerror = function() {
        reject(Error("Network Error"));
      };
  
      // Make the request
      req.send();
    });
};

export function tryParseJSON (jsonString){
  try {
      var o = JSON.parse(jsonString);

      // Handle non-exception-throwing cases:
      // Neither JSON.parse(false) or JSON.parse(1234) throw errors, hence the type-checking,
      // but... JSON.parse(null) returns null, and typeof null === "object", 
      // so we must check for that, too. Thankfully, null is falsey, so this suffices:
      if (o && typeof o === "object") {
          return o;
      }
  }
  catch (e) { }

  return false;
};

export function isInViewport(element) {
  if (!element) return false;
  const rect = element.getBoundingClientRect();
  return (
      rect.top >= 0 &&
      rect.left >= 0 &&
      rect.bottom <= (window.innerHeight || document.documentElement.clientHeight) &&
      rect.right <= (window.innerWidth || document.documentElement.clientWidth)
  );
};

export function getUrlParameter(name) {
  var regex = new RegExp("[\\?&]" + name + "=([^&#]*)");
  var results = regex.exec(location.search);
  return results === null ? "" : decodeURIComponent(results[1]);
}

export function isElementHidden(el) {
  if (!el) return true; 
  var style = window.getComputedStyle(el);
  return (style.display === 'none');
}

export function checkIE() {
  return "-ms-scroll-limit" in document.documentElement.style &&
         "-ms-ime-align" in document.documentElement.style;
}

export function PromiseAllSettledPolyfill() {
  if(!Promise.allSettled) {
    Promise.allSettled = function(promises) {
      return Promise.all(promises.map(p => Promise.resolve(p).then(value => ({
        status: 'fulfilled',
        value
      }), reason => ({
        status: 'rejected',
        reason
      }))));
    };
  }
}

export function ElementClosestPolyfill() {
  //see https://developer.mozilla.org/en-US/docs/Web/API/Element/closest#polyfill
  if (!Element.prototype.matches) {
    Element.prototype.matches =
      Element.prototype.msMatchesSelector ||
      Element.prototype.webkitMatchesSelector;
  }
  
  if (!Element.prototype.closest) {
    Element.prototype.closest = function(s) {
      var el = this;
      do {
        if (Element.prototype.matches.call(el, s)) return el;
        el = el.parentElement || el.parentNode;
      } while (el !== null && el.nodeType === 1);
      return null;
    };
  }
}
