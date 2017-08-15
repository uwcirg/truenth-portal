var gulp = require('gulp');
var source = require('vinyl-source-stream');
var request = require('request');
var merge = require('merge2');
var concat = require('gulp-concat');
var buffer = require('gulp-buffer');
var del = require('del');
var uglify = require('gulp-uglify');
var rename = require('gulp-rename');
var scanner = require('i18next-scanner');
//var converter = require('./static/js/i18next-conversion');

gulp.task('i18next-extraction', function() {
    return gulp.src(['static/**/*.{js,html}'])
        .pipe(scanner({
            lngs: ['en'], // supported languages
            keySeparator: "|",
            nsSeparator: "|",
            attr: {
                list: ['data-i18n'],
                extensions: ['.js', '.html', '.htm']
            },
            func: {
                list: ['i18next.t', 'i18n.t'],
                extensions: ['.js', '.jsx']
            },
            resource: {
                // the source path is relative to current working directory
                savePath: './src/translation.json'
            }
        }))
        .pipe(gulp.dest('translations/js'));
});

gulp.task('i18nextConversions', function() {
    const path = require('path');
    //const { readFileSync, writeFileSync } = require('fs');
    const fs = require('fs');
    // const {
    //   i18nextToPo,
    //   i18nextToPot,
    //   i18nextToMo,
    //   gettextToI18next,
    // } = require('i18next-conv');
    const i18nextConv = require('i18next-conv');


    const source = path.join(__dirname, './translations/js/src/translation.json');
    const options = {/* you options here */}

    function save(target) {
      return result => {
        fs.writeFileSync(target, result);
      };
    }
   /*
    *converting json to pot to be sent to translator
    */
    i18nextConv.i18nextToPot('en', fs.readFileSync(source), options).then(save(path.join(__dirname, './translations/js/src/translation.pot')));

    /*
     * converting po to json files
     * note translating existing po file to json, which will be consumed by the front end
     * this assumes that text has been extracted from js file, translated into POT and then returned as po file from translator
     */
    i18nextConv.gettextToI18next('en-US', fs.readFileSync(path.join(__dirname,'./translations/en_US/LC_MESSAGES/messages.po')), options)
    .then(save(path.join(__dirname,'./translations/js/dest/locales/en_US/translation.json')));
    i18nextConv.gettextToI18next('en-AU', fs.readFileSync(path.join(__dirname,'./translations/en_AU/LC_MESSAGES/messages.po')), options)
    .then(save(path.join(__dirname,'./translations/js/dest/locales/en_AU/translation.json')));
});

gulp.task('i18nextConcatScripts', function() {

  var i18nextMain = request('https://unpkg.com/i18next/i18next.js')
    .pipe(source('i18nextMain.js'));
  var i18nextXHRBackend = request('https://unpkg.com/i18next-xhr-backend/i18nextXHRBackend.js')
    .pipe(source('i18nextXHRBackend.js'));
  var i18nextLnDetection = request('https://unpkg.com/i18next-browser-languagedetector/i18nextBrowserLanguageDetector.js')
    .pipe(source('i18nextBrowserLanguageDetector.js'));

  return merge(i18nextMain, i18nextXHRBackend, i18nextLnDetection)
    .pipe(buffer())
    .pipe(concat('i18next.js'))
    .pipe(gulp.dest('static/js'));
});

gulp.task("minifyi18nextScripts", ["i18nextConcatScripts"], function() {
  return gulp.src("static/js/i18next.js")
    .pipe(uglify())
    .pipe(rename('i18next.min.js'))
    .pipe(gulp.dest('static/js'));
});

gulp.task('clean', function() {
  del(['static/js/i18next*.js']);
});

gulp.task('default', ['clean', 'minifyi18nextScripts', 'i18next-extraction', 'i18nextConversions'], function() {
    console.log('running default task..');
})