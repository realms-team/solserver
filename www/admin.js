// Global variables
var timeout;
var sites   = [] // a list of sites

//------------------ Init functions ------------------------------------------//

function load_sites(){
    // set default time to current time minux 5 mins
    isoTime = new Date().toISOString()

    var solType     = "SOL_TYPE_SOLMANAGER_STATS";
    var encType     = encodeURIComponent(solType);
    var encTime     = encodeURIComponent(isoTime);
    $.getJSON("api/v1/jsonp/all/" + encType + "/time/" + encTime, set_sites);
}

//------------------ Main functions ------------------------------------------//

// Populate the list of sites
function set_sites(data){
    for (var i=0; i < data.length; i++) {
        $("#site_list").append(
            '<div class="col-sm-3">' +
                '<div class="panel panel-primary">' +
                    '<div class="panel-heading">' +
                        '<h3 class="panel-title">' + data[i].value.site + '</h3>' +
                    '</div>' +
                    '<div class="panel-body">' +
                        '<b>sol_version:</b> ' + data[i].value.sol_version + '<br>' +
                        '<b>solmanager_version:</b> ' + data[i].value.solmanager_version + '<br>' +
                        '<b>sdk_version:</b> ' + data[i].value.sdk_version + '<br>' +
                    '</div>' +
                '</div>' +
            '</div>'
            );
        sites[i] = data
        console.log(data[i].value.site + ":" + data[i].value.sol_version);
    }
}

//----------------Interface Listeners ---------------------------------------//

$(document).ready(function() {
    $("#refresh").click(function(event) {
      load_sites();
    });
});

//------------------ Helpers ------------------------------------------------//
