
const sleep = (milliseconds) => {
    return new Promise(resolve => setTimeout(resolve, milliseconds))
}

function js_Load() {
    document.body.style.visibility = 'visible';
}


function updateTabIndicator(){
    sleep(250).then(() => {
        $(".tabs").tabs('updateTabIndicator');
    });
}

function init_select(){
    // #tags-select is a native control styled by the design system; running
    // Materialize over it would replace it with its own dropdown.
    $('select').not('#tags-select').formSelect({
        dropdownOptions:{
            container: document.body,
            constrainWidth: true,
        }
    });
    $('input').each(function(index, el) {
        if ($(this).attr('data-autocomplete-options')){
            let options_list = $(this).attr('data-autocomplete-options').split(',');
            let options_dict = options_list.map(x => ({'key': x, 'val': null}));
            options_dict = options_dict.reduce(function(map, obj) {
                map[obj.key] = obj.val;
                return map;
            }, {});
            $(this).autocomplete({
                data: options_dict,
                dropdownOptions:{
                    container: document.body,
                }
            });
            if ($(this).attr('data-auto-only') === 'true') {
                $(this).on('blur', function(e) {
                    if (options_list.includes($(this).val()) === false) {
                        $(this).val('');
                    }
                });
            }
        }
    });
}

function init_copy_btn(parent_class){
    $(".copy-btn").on('click', function(e) {
        let target_text = $(this).closest(parent_class).find('.copy-target').text();
        let copy_input = $("#copy-input");
        copy_input.val(target_text);
        copy_input.removeClass("hide");
        copy_input.select();
        document.execCommand("copy");
        copy_input.addClass("hide");
        copy_input.val('');
        M.toast({html: "Copied to Clipboard"})
    });
}

function hide_sidenav() {
    document.body.classList.add('sidenav-hidden');
    localStorage.setItem('sidenav_hidden', 'true');
}

function no_sidebar() {
    document.body.classList.add('sidenav-hidden', 'no-sidenav');
    $("#no-sidenav").removeClass('hide');
    localStorage.setItem('sidenav_hidden', 'no_sidebar');
}

function show_sidenav(){
    document.body.classList.remove('sidenav-hidden', 'no-sidenav');
    $("#no-sidenav").addClass('hide');
    localStorage.removeItem('sidenav_hidden');
}

function toggle_drawer(open) {
    document.body.classList.toggle('drawer-open', open === undefined
        ? !document.body.classList.contains('drawer-open')
        : open);
}

function apply_settings(settings){
    // theme
    if (settings['user_theme'] != "None" && settings['user_theme'].length > 1) {
        console.log(settings['user_theme'].length)
        localStorage.setItem('mode', settings['user_theme']);
        document.documentElement.setAttribute('data-theme', settings['user_theme']);
    } else {
        localStorage.setItem('mode', settings['settings_theme']);
        document.documentElement.setAttribute('data-theme', settings['settings_theme']);
    }
    // accent
    if (settings['user_accent'] != "None" && settings['user_accent'].length > 1) {
        localStorage.setItem('accent', settings['user_accent']);
        document.documentElement.setAttribute('data-accent', settings['user_accent']);
    } else {
        localStorage.setItem('accent', settings['settings_accent']);
        document.documentElement.setAttribute('data-accent', settings['settings_accent']);
    }
    if (settings['settings_sidebar_default'] == "closed"){
        localStorage.setItem('sidenav_hidden', 'true');
    } else if (settings['settings_sidebar_default'] == "open"){
        localStorage.setItem('sidenav_hidden', 'false');
    } else if (settings['settings_sidebar_default'] == "no_sidebar"){
        localStorage.setItem('sidenav_hidden', 'no_sidebar');
    }
    if (settings['user_sidebar_default'] == "closed"){
        localStorage.setItem('sidenav_hidden', 'true');
    } else if (settings['user_sidebar_default'] == "open"){
        localStorage.setItem('sidenav_hidden', 'false');
    } else if (settings['user_sidebar_default'] == "no_sidebar"){
        localStorage.setItem('sidenav_hidden', 'no_sidebar');
    }
    if (localStorage.getItem('sidenav_hidden') === 'true'){
        hide_sidenav();
    } else if (localStorage.getItem('sidenav_hidden') === 'no_sidebar'){
        no_sidebar();
    } else if (settings['user_name'].length < 1) {
        no_sidebar();
    }
}

//--------------------------------------------------------------------------------------
// Document ready function
//--------------------------------------------------------------------------------------
$(document).ready(function () {
    "use strict";
    apply_settings({
        settings_theme: $("#settings-theme").val(),
        settings_accent: $("#settings-accent").val(),
        settings_sidebar_default: $("#settings-sidebar_default").val(),
        user_name: $("#user-name").val(),
        user_theme: $("#user-theme").val(),
        user_accent: $("#user-accent").val(),
        user_sidebar_default: $("#user-sidebar_default").val(),
    });

    //  INITS
    init_select();

    $("#update-message-modal").modal({
        dismissible: false
    });
    // Do not put an announcement in front of the sign-in form; it is modal and
    // undismissable until read, which made logging in impossible on a phone.
    // trim(): the template leaves whitespace inside the content div, which made
    // this test pass on an empty message and opened a blank modal every load.
    if ($("#update-message-content").text().trim().length > 1 && $("#user-name").val().length > 0){
        $("#update-message-modal").modal('open');
    }
    $("#update-message-read-btn").on('click', function(e) {
       $.ajax({
           url: $(this).attr('data-url'),
           type: 'GET',
           success: function(data){
               $("#update-message-modal").modal('close');
           }
       });
    });

    $("#hide-sidenav").on('click', function(e) {
        hide_sidenav();
    });

    $("#show-sidenav .material-icons-outlined").on('click', function(e) {
        show_sidenav();
    });

    $("#sidenav-mobile-toggle-btn, #sidenav-scrim").on('click', function(e) {
        e.preventDefault();
        toggle_drawer();
    });

    // close the drawer after navigating on a phone
    $("#main-sidenav .side-link").on('click', function() {
        toggle_drawer(false);
    });

    $(".dropdown-trigger").dropdown({
        coverTrigger: false,
        constrainWidth: false
    });
    $(".tabs").tabs();

    // Fab
    $(".fixed-action-btn").floatingActionButton();
    $(".fixed-action-btn.horizontal").floatingActionButton({
        direction: "left"
    });
    $(".fixed-action-btn.click-to-toggle").floatingActionButton({
        hoverEnabled: false
    });
    $(".fixed-action-btn.toolbar").floatingActionButton({
        toolbarEnabled: true
    });
    $('.tap-target').tapTarget();
    $('.tap-target').tapTarget('open');

    // Detect touch screen and enable scrollbar if necessary
    function is_touch_device() {
        try {
            document.createEvent("TouchEvent");
            return true;
        } catch (e) {
            return false;
        }
    }
    if (is_touch_device()) {
        $("#nav-mobile").css({
            overflow: "auto"
        });
    }


    // make jquery contains selector case unaware
    jQuery.expr[':'].contains = function(a, i, m) {
        return jQuery(a).text().toUpperCase()
            .indexOf(m[3].toUpperCase()) >= 0;
    };

});



