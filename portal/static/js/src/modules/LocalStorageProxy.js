export default {
    isLocalStorageSupported: function() {
        try {
            return "localStorage" in window && window["localStorage"] !== null;
        } catch(e) {
            return false;
        }
    },
    put: function(key, jsonData, expirationMin){
        if (!expirationMin) expirationMin = 60 * 24; //one day
		if (!this.isLocalStorageSupported()){
            return false;
        }
		var expirationMS = expirationMin * 60 * 1000;
		var record = {value: JSON.stringify(jsonData), timestamp: new Date().getTime() + expirationMS};
		localStorage.setItem(key, JSON.stringify(record));
		return jsonData;
	},
	get: function(key){
		if (!this.isLocalStorageSupported()){
            return false;
        }
        if (!localStorage.getItem(key)) {
            return false;
        }
        var record = JSON.parse(localStorage.getItem(key));
        console.log("data? ", record);
		if (!record){return false;}
		return (new Date().getTime() < record.timestamp && JSON.parse(record.value));
	}
};

