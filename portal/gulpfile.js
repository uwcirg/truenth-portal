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
const path = require('path');
const fs = require('fs');
const mkdirp = require('mkdirp');
const i18nextConv = require('i18next-conv');
const translationJsonSource = path.join(__dirname, './translations/js/src/translation.json');
const translationPOTSource = path.join(__dirname, './translations/js/src/translation.pot');

/*
 * extracting text from js into json file for translation
 */
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
                // the source path is relative to current working directory as specified in the destination folder
                savePath: './src/translation.json'
            }
        }))
        .pipe(gulp.dest('translations/js'));
});
/*
 * convert json to pot for translator's consumption - definition file
 * convert po file returned from translator to json file for consumption by frontend
 */
gulp.task('i18nextConversions', ['minifyi18nextScripts', 'i18next-extraction'], function() {
    
    const options = {/* you options here */}

    function save(target) {
      return result => {
        fs.openSync(target, 'w+', function(err, fd) {
            if (err) console.log("error open: " + target);
            else {
              fs.writeFileSync(target, result);
              fs.close(fd, function(err) {
                if (err) console.log("error closing file: " + target + " : " + err);
              });
            };
        });
      };
    }
   /*
    *converting json to pot to be sent to translator
    */
    fs.open(translationJsonSource, 'w+', function(err, fd) {
      if (err) console.log("Error open file: " + translationJsonSource);
      else {
        i18nextConv.i18nextToPot('en', fs.readFileSync(translationJsonSource), options).then(save(translationPOTSource));
        fs.close(fd, function(err) {
          console.log("Error closing file: " +  translationJsonSource + " : " + err);
        });
      };
    });

    /*
     * converting po to json files
     * note translating existing po file to json, which will be consumed by the front end
     * this assumes that text has been extracted from js file, translated into POT and then returned as po file from translator
     */
     /*
      * the path where JS will consume the json files will translated text
      * note json files for specific locales
      */
     const en_us_dir = path.join(__dirname,'./static/files/locales/en-US');
     const en_au_dir = path.join(__dirname,'./static/files/locales/en-AU');

     // mkdirp(en_us_dir, function(err) {
     //    if (err) console.err("error occurred creating locales en-US directory: " + err);
     //    else console.log("en-US directory created");
     // });
     // mkdirp(en_au_dir, function(err) {
     //    if (err) console.err("error occurred creating locales en-AU directory: " + err);
     //    else console.log("en-AU directory created");
     // });
     /*
      * translating po file to json for en-US locale
      */
    fs.open(en_us_dir+"/translation.json", 'w+', function(err, fd) {
      if (err) console.log("error occurred writing en-us json: " + err);
      else {
        i18nextConv.gettextToI18next('en-US', fs.readFileSync(path.join(__dirname,'./translations/en_US/LC_MESSAGES/messages.po')), options)
        .then(save(en_us_dir+"/translation.json"));
        fs.close(fd, function(err) {
            if (err) console.log("error occurred closing " + en_us_dir + "/translation.json");
        });
      };
    });
    /*
     * translating po file to json for en-AU locale
     */
    fs.open(en_au_dir+"/translation.json", 'w+', function(err, fd) {
      if (err) console.log("error occurred writing en-au json: " + err);
      else {
        i18nextConv.gettextToI18next('en-AU', fs.readFileSync(path.join(__dirname,'./translations/en_AU/LC_MESSAGES/messages.po')), options)
        .then(save(en_au_dir+"/translation.json"));
        fs.close(fd, function(err) {
          if (err) console.log("error occurred closing " + en_au_dir + "/translation.json");
        });
      };
    });
});
/*
 * concating all necessary i18next JS files into one
 */
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
/*
 * minify combined i18next JS file
 */
gulp.task("minifyi18nextScripts", ["i18nextConcatScripts"], function() {
  return gulp.src("static/js/i18next.js")
    .pipe(uglify())
    .pipe(rename('i18next.min.js'))
    .pipe(gulp.dest('static/js'));
});
/*
 * clean all generated files
 */
gulp.task('clean', function() {
  del(['static/js/i18next*.js', 'static/files/**/translation.json', 'translations/js/src/*']);
});

gulp.task('default', ['clean', 'minifyi18nextScripts', 'i18next-extraction', 'i18nextConversions'], function() {
    console.log('running default task..');
})