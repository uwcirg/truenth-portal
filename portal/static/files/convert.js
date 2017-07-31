/*
 *  Sample code to translate JSON file into POT, po and mo files
 * 
 */
var exports = module.exports = {};
exports.convert = function(lng) {
	const path = require('path');
	const { readFileSync, writeFileSync } = require('fs');
	const {
	  i18nextToPo,
	  i18nextToPot,
	  i18nextToMo
	} = require('i18next-conv');

	const source = path.join(__dirname, '../i8next/dest/locales/en/translation.json');
	const options = {/* you options here */}

	function save(target) {
	  return result => {
	    writeFileSync(target, result);
	  };
	}

	//path.join(__dirname, '../i8next/dest/locales/en/translation.json')
	i18nextToPo(lng, readFileSync(source), options).then(save(path.join(__dirname, '../i8next/dest/locales/' + lng + '/translation.po')));
	i18nextToPot(lng, readFileSync(source), options).then(save(path.join(__dirname,'../i8next/dest/locales/' + lng + '/translation.pot')));
	i18nextToMo(lng, readFileSync(source), options).then(save(path.join(__dirname, '../i8next/dest/locales/' + lng + '/translation.mo')));

};