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
var concatPo = require('gulp-concat-po');
const path = require('path');
const fs = require('fs');
const i18nextConv = require('i18next-conv');
const translationJsonSource = path.join(__dirname, './translations/js/src/translation.json');
const translationPOTSource = path.join(__dirname, './translations/js/src/translation.pot');


function save(target) {
  return result => {
    fs.writeFileSync(target, result);
  };
};

/*
 * extracting text from js into json file
 */
gulp.task('i18next-extraction', ['minifyi18nextScripts'], function() {
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
gulp.task('i18nextConvertJSONToPOT', ['i18next-extraction'], function() {
    
    const options = {/* you options here */}
   /*
    * converting json to pot
    */
    console.log("converting JSON to POT...")
    i18nextConv.i18nextToPot('en', fs.readFileSync(translationJsonSource), options).then(save(translationPOTSource));

});

/*
 * append newly generated pot file to the existing messages.pot
 */
gulp.task('combinePotFiles', ['i18nextConvertJSONToPOT'], function() {
    del(['translations/messages-new.pot']);
    return gulp.src(['translations/messages.pot', 'translations/js/src/translation.pot'])
          .pipe(concatPo('messages.pot'))
          .pipe(gulp.dest('translations'));
});

gulp.task('i18nextConvertPOToJSON', ['combinePotFiles'], function() {
  /*
   * converting po to json files
   * note translating existing po file to json, which will be consumed by the front end
   * this assumes that 
   *    1. text has been extracted from js file into JSON file
   *    2. translated JSON into POT
   *    3. merge new POT into main POT file [need to check about this step]
   *    4. po is returned from translator after uploading POT file from #3
   */
   /*
    * the path to the converted json file, where JS will consume the json files for translated text
    * note json files are saved for specific locales from each po file of corresponding locale
    */
  console.log("converting po to json...")
  const dest_en_us_dir = path.join(__dirname,'./static/files/locales/en-US');
  const dest_en_au_dir = path.join(__dirname,'./static/files/locales/en-AU');
  const options = {/* you options here */}

   /*
    * translating po file to json for en-US locale
    */
  fs.open(dest_en_us_dir+"/translation.json", 'w+', function(err, fd) {
    if (err) console.log("error occurred writing en-us json: " + err);
    else {
      i18nextConv.gettextToI18next('en-US', fs.readFileSync(path.join(__dirname,'./translations/en_US/LC_MESSAGES/messages.po')), options)
      .then(save(dest_en_us_dir+"/translation.json"));
      fs.close(fd, function(err) {
          if (err) console.log("error occurred closing " + dest_en_us_dir + "/translation.json");
      });
    };
  });
  /*
   * translating po file to json for en-AU locale
   */
  fs.open(dest_en_au_dir+"/translation.json", 'w+', function(err, fd) {
    if (err) console.log("error occurred writing en-au json: " + err);
    else {
      i18nextConv.gettextToI18next('en-AU', fs.readFileSync(path.join(__dirname,'./translations/en_AU/LC_MESSAGES/messages.po')), options)
      .then(save(dest_en_au_dir+"/translation.json"));
      fs.close(fd, function(err) {
        if (err) console.log("error occurred closing " + dest_en_au_dir + "/translation.json");
      });
    };
  });
})
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

/*
 * NOTE, the task - converting po to json file is not included, as I think we need to upload pot to smartling first to have 
   it return the po files
   so I think we need to run 'i18nextConvertPOToJSON' task separately
 */
gulp.task('default', ['minifyi18nextScripts', 'i18next-extraction', 'combinePotFiles'], function() {
    console.log('running default task..');
})