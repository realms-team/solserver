// LINK LIMITS
var GOOD_LINK_RSSI      = -70;
var MEDIUM_LINK_RSSI    = -80;
var GOOD_LINK_PDR       = 80;
var MEDIUM_LINK_PDR     = 50;

// LINK COLOR
var GOOD_LINK_COLOR     = "#00ff00"     // green
var MEDIUM_LINK_COLOR   = "#ffff00"     // orange
var BAD_LINK_COLOR      = "#ffff00"     // red
var UNKNOWN_LINK_COLOR  = "#ffffff"     // white

// Global variables
var map;
var mote_list   = [];         // a list of motes {mac,marker}
var link_list   = [];         // a list of links
var timeout;
var infoWindow;
var SITE_TIME_OFFSET    = -3
var DEFAULT_PDR         = 101 // init to impossible value
var board_colors        = {"#c33c1c":null,"#dbd60d":null,"#acd2cd":null,"#ff9966":null}


//------------------ Init functions ------------------------------------------//

function initMap() {
    map = new google.maps.Map(document.getElementById('map'), {
        center: new google.maps.LatLng(0, 0),
        zoom: 18,
        scaleControl: true,
        tilt: 0,
    });
    map.setMapTypeId(google.maps.MapTypeId.SATELLITE);

    // set date
    $( "#datepicker" ).datepicker();
    $( "#datepicker" ).datepicker('setDate', 'today');

    // set time
    defaultDate = new Date();
    defaultDate.setTime(defaultDate.getTime());
    $('#timepicker').timepicker({
        showNowButton: true,
        showDeselectButton: true,
        showCloseButton: true,
    });
    $('#timepicker').timepicker('setTime', defaultDate.toLocaleTimeString(
                                'es-AR', { hour: "numeric",
                                minute: "numeric"}));
    load_data(1);
}

function load_data(loop){
    clearLinks();

    // set default time to UTC time
    var date        = $("#datepicker").datepicker('getDate');
    var time        = $("#timepicker").timepicker('getTime').split(':');
    var localOffset = new Date().getTimezoneOffset()/60;
    date.setHours(parseInt(time[0]), time[1]);

    // get host and site name
    var host        = window.location.origin
    var path        = window.location.pathname.split("/map")[0]
    var sitename    = $("#sitename").val()

    // display motes and links
    get_motes(host, path, sitename, date);
    var delay = function() { get_links(host, path, sitename, date) };
    window.setTimeout(delay,500);

    if (loop == 1)
        timeout = setTimeout(load_data, 30000);
    else
        clearTimeout(timeout)
}

//------------------ Main functions ------------------------------------------//

// request the server for mote information
function get_motes(host, path, sitename, date){
    var solType     = "SOL_TYPE_DUST_NOTIF_HRNEIGHBORS";
    var encType     = encodeURIComponent(solType);
    var isoTime     = date.toISOString();
    var encTime     = encodeURIComponent(isoTime);
    $.getJSON(host+ path +
        "/api/v1/jsonp/"+sitename+"/" + encType +
        "/time/" + encTime, create_motes);
}

// request the server for links information
function get_links(host, path, sitename, date){
    var solType     = "SOL_TYPE_DUST_SNAPSHOT";
    var encType     = encodeURIComponent(solType);
    var isoTime     = date.toISOString();
    var encTime     = encodeURIComponent(isoTime);
    $.getJSON(host+ path +
        "/api/v1/jsonp/"+sitename+"/" + encType +
        "/time/" + encTime, create_links);
}

// populate the motes list
function create_motes(data){
    var bounds = new google.maps.LatLngBounds();
    var loc;

    for (var i=0; i < data.length; i++) {
        mote_list.push({
            "mac"       : data[i].mac,
            "marker"    : null
        });
        loc = new google.maps.LatLng(
            data[i].value.latitude,
            data[i].value.longitude
        );
        bounds.extend(loc);
        updateMote(
            data[i].mac,
            data[i].value.latitude,
            data[i].value.longitude,
            data[i].value.board
        );

        // fit map boundaries
        map.fitBounds(bounds);
        map.panToBounds(bounds);
    }
}
function create_links(data){
    // loop through snapshot
    if (Object.keys(data).length > 0) {

        // add the manager to the map
        create_manager(data);

        motes = data[0].value.mote
        //for each mote
        for (var i in motes) {
            m = motes[i]
              //for each path
              for (var j in m.paths){
                  n = m.paths[j];
                  if ((n.macAddress != null) && (n.direction == 2 || n.direction == 3)){
                    var crd1 = getLocationFromMac(m.macAddress);
                    var crd2 = getLocationFromMac(n.macAddress)
                    if (crd1 != null && crd2 != null){
                        var lineCoords = [crd1, crd2];

                        // get metric
                        var pdr = n.quality;
                        var rssi = Math.min(n.rssiDestSrc,n.rssiSrcDest);

                        // create link
                        var color   = getLinkColor(rssi, pdr);
                        var dist    = calcDistance(lineCoords[0],lineCoords[1])
                        // set line parameters
                        if (pdr == DEFAULT_PDR)
                          s_pdr = "No Tx"
                        else
                          s_pdr = pdr + "%"
                        var content =   "RSSI: " + rssi + "dBm<br>" +
                                        "PDR: " + s_pdr + "<br>" +
                                        "Distance: " + dist + "m"
                        var l = createPolyline(lineCoords, content, color);
                        var newLink = {
                            "pline" :   l,
                            "metric":   {
                                    "rssi"  : rssi,
                                    "pdr"   : pdr,
                                }
                        }
                        links.push(newLink);
                    }
                }
            }
        }
    }
}

function create_manager(data){
    var color   = getMoteColor(data[0].value.board);

    mote_list.push({
        "mac"         : data[0].mac,
        "marker"      : createMarker(
            data[0].value.latitude,
            data[0].value.longitude,
            "Manager<br>"+data[0].mac+"<br>"+data[0].value.board,
            color)
    });
}
//----------------Interface Listeners ---------------------------------------//

$(document).ready(function() {
    $("#next_time").click(function(event) {
        var selectedTime =  $('#timepicker').timepicker('getTimeAsDate');
        // add 5 minutes
        var newDate = new Date(selectedTime.getTime() + 5*60000)
        str_date = newDate.getHours().toString() + ":" + newDate.getMinutes().toString();
        $('#timepicker').timepicker('setTime', str_date);
        load_data(0);
    });
});

$(document).ready(function() {
    $("#prev_time").click(function(event) {
        var selectedTime =  $('#timepicker').timepicker('getTimeAsDate');
        // remove 5 minutes
        var newDate = new Date(selectedTime.getTime() - 5*60000)
        str_date = newDate.getHours().toString() + ":" + newDate.getMinutes().toString();
        $('#timepicker').timepicker('setTime', str_date);
        load_data(0)
    });
});

//------------------ Helpers ------------------------------------------------//

function clearLinks(){
    // remove links
    for (var i=0; i<links.length; i++) {
        if (i in links){
            links[i].pline.setMap(null);
        }
    }
    links = [];
    links.length = 0;
}

function getLinkColor(rssi, pdr){
    var metric = $("#metric").val()

    if (metric == "rssi"){
        if (rssi > GOOD_LINK_RSSI)
            return GOOD_LINK_COLOR;
        else if (rssi >= MEDIUM_LINK_RSSI && rssi <= GOOD_LINK_RSSI)
            return MEDIUM_LINK_COLOR;
        else
            return BAD_LINK_COLOR;
    }
    else if (metric == "pdr"){
        if (pdr == DEFAULT_PDR)
            return UNKNOWN_LINK_COLOR;
        if (pdr >= GOOD_LINK_PDR)
            return GOOD_LINK_COLOR;
        else if (pdr > MEDIUM_LINK_PDR && pdr < GOOD_LINK_PDR)
            return MEDIUM_LINK_COLOR;
    }
}

function getMoteColor(board){
    if (board == null)
        board = "unknown"
    for (var color in board_colors){
        if (board_colors[color] === null){
            board_colors[color] = board;
            return color;
        }
        else if (board_colors[color] === board){
            return color
        }
    }
    // return default color if board_color is too small
    return "#FFF"
}

function updateMote(mac, lat, lng, board){
    var moteId  = null;
    var color   = getMoteColor(board)
    for (var i=0; i<mote_list.length; i++) {
        if (mote_list[i].mac == mac){
            var content = mac + "<br>"
            if (board != null)
              content += board + "<br>"
            if (mote_list[i].marker == null){
                mote_list[i].marker = createMarker(lat, lng, content, color);
            } else if (mote_list[i].marker.position.lat() != lat ||
                        mote_list[i].marker.position.lng() != lng) {
                mote_list[i].marker.setMap(null);
                mote_list[i].marker = createMarker(lat, lng, content, color);
            }
        }
    }
}

function createMarker(lat, lng, content, color){
    // create Markers
    var myLatLng = new google.maps.LatLng(lat, lng)
    var marker = new google.maps.Marker({
        position: myLatLng,
        map: map,
        icon: pinSymbol(color),
    });
    // add popup listener
    infoBox(map, marker, content);
    return marker;
}

function createPolyline(lineCoordinates, content, color){
    var line = new google.maps.Polyline({
          path: lineCoordinates,
          geodesic: true,
          strokeColor: color,
          strokeWeight: 2
    });
    if (color != UNKNOWN_LINK_COLOR){
        line.setMap(map);
        infoBox(map, line, content);
    }
    return line;
}

function getLocationFromMac(mac){
    for( i=0; i<mote_list.length; i++ ) {
        if (mote_list[i].mac == mac){
            return mote_list[i].marker.position;
        }
    }
    console.log("MAC not found:" + mac)
    return null;
}

// calculates distance between two points in meters
function calcDistance(p1, p2) {
    return (google.maps.geometry.spherical.computeDistanceBetween(p1, p2)).toFixed(2);
}

/*Function that shows a window with the content or info
 about the marker (sensor location)*/

function infoBox(map, marker, content) {
    infoWindow = new google.maps.InfoWindow();
    // Attaching a click event to the current marker
    google.maps.event.addListener(marker, "click", function(e) {
        infoWindow.setPosition(e.latLng);
        infoWindow.setContent(content);
        infoWindow.open(map, marker);
        var iw_container = $(".gm-style-iw").parent();
        iw_container.stop().hide();
        iw_container.fadeIn(300);
    });
}

// Function that create a vectorial image of a marker with the given color
function pinSymbol(color) {
    return {
        path: 'M 0,0 C -2,-20 -10,-22 -10,-30 A 10,10 0 1,1 10,-30 C 10,-22 2,-20 0,0 z M -2,-30 a 2,2 0 1,1 4,0 2,2 0 1,1 -4,0',
        fillColor: color,
        fillOpacity: 1,
        strokeColor: '#000',
        strokeWeight: 2,
        scale: 1,
   };
}
