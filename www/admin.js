// Global variables
var timeout;

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
                        '<span class="col-xs-8 panel-title">' + data[i].value.site + "</span>" +
                        '<button class="update_btn col-xs-4 btn btn-default btn-xs"'+
                        'onclick=start_update(this,\''+data[i].value.site+'\');'+'title="Update">'+
                            '<span class="glyphicon glyphicon-arrow-up" aria-hidden="true"></span>' +
                        '</button>'+
                        '<br>' +
                    '</div>' +
                    '<div class="panel-body">' +
                        '<b>sol_version:</b> ' + data[i].value.sol_version + '<br>' +
                        '<b>solmanager_version:</b> ' + data[i].value.solmanager_version + '<br>' +
                        '<b>sdk_version:</b> ' + data[i].value.sdk_version + '<br>' +
                    '</div>' +
                    '<div class="text-right">' +
                        '<small>' + data[i].timestamp + "</small>&nbsp;" +
                    '</div>' +
                '</div>' +
            '</div>'
            );
    }
}

// Tell the server to start the update process
function start_update(self,site_name){
    var token = prompt("Please give site token","");
    var jqxhr = $.ajax({
                        url :"api/v1/setaction/",
                        type:"POST",
                        headers: { "X-REALMS-Token": token },
                        data: JSON.stringify({ "action": "update",
                               "site": site_name
                               }),
                        contentType:"application/json"
                    });
    jqxhr.done(function() {
        $("#feedback").append("> Update started for site "+site_name+"<br>");
    })
    jqxhr.fail(function(xhr, status) {
        $("#feedback").append("> Error: "+xhr.responseText+"<br>");
    })
}

function _update_handler(data, status){
    console.log("toto")
}

//----------------Interface Listeners ---------------------------------------//

$(document).ready(function() {
    $("#refresh").click(function(event) {
      load_sites();
    });
});

//------------------ Helpers ------------------------------------------------//
