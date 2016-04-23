// LINK LIMITS
var GOOD_LINK_LIMIT     = -70;
var MEDIUM_LINK_LIMIT   = -80;
var BAD_LINK_LIMIT      = -90;

// LINK COLOR
var GOOD_LINK_COLOR     = "#00ff00"     // green
var MEDIUM_LINK_COLOR   = "#ffff00"     // orange
var BAD_LINK_COLOR      = "#ffff00"     // red

// Global variables
var map;
var MOTES = [];         // a list of [mac, Marker]
var LINKS = [];         // a list of [Polyline, rssi]
var timeout;
var infoWindow;

//------------------ Init functions ------------------------------------------//

function initMap() {
    map = new google.maps.Map(document.getElementById('map'), {
        center: {lat: -33.114974, lng: -68.481041},
        zoom: 18
    });
    map.setMapTypeId(google.maps.MapTypeId.SATELLITE);

    load_data();

    $('#timepicker').timepicker({
        showNowButton: true,
        showDeselectButton: true,
        defaultTime: '',  // removes the highlighted time for when the input is empty.
        showCloseButton: true
    });
    $( "#datepicker" ).datepicker();
}

function load_data(utcTime, loop){
    clearLinks();

    // if time not given, set default time to current time minux 5 mins
    if (utcTime == null){
        currentTime = new Date();
        currentTime.setMinutes(currentTime.getMinutes() - 30)
        utcTime     = currentTime.toISOString();
    }

    // MOTE CREATE
    var solType     = "SOL_TYPE_DUST_EVENTMOTECREATE";
    var encType     = encodeURIComponent(solType);
    var encTime     = encodeURIComponent(utcTime);
    $.getJSON("jsonp/ARG_junin/" + encType + "/time/" + encTime, create_mote);

    // LINKS CREATE
    solType         = "SOL_TYPE_DUST_NOTIF_HRNEIGHBORS";
    encType         = encodeURIComponent(solType);
    $.getJSON("jsonp/ARG_junin/" + encType + "/time/" + encTime, create_links);

    if (loop != 0)
        timeout = setTimeout(load_data, 30000);
    else
        clearTimeout(timeout)
}

//------------------ Main functions ------------------------------------------//

function create_mote(data){
    for (var i=0; i < data.length; i++) {
        // populate table
        MOTES[data[i].value.moteId] = [data[i].value.macAddress, null]
    }
}

function create_links(data){
    for (var i=0; i < data.length; i++) {
        udpateMote(data[i].mac, data[i].value.latitude,data[i].value.longitude);
    }
    for (var i=0; i < data.length; i++) {
        for (var j=0; j<data[i].value.neighbors.length; j++){
            var neighbor = data[i].value.neighbors[j];
            if (neighbor.neighborId in MOTES){
                var crd1 = getLocationFromMac(data[i].mac);
                var crd2 = getLocationFromId(neighbor.neighborId)
                if (crd1 != null && crd2 != null){
                    var lineCoordinates = [
                        crd1,
                        crd2
                    ];
                    var link = getLink(crd1, crd2);

                    // update link if already exists and new rssi is worst
                    if (link != null){
                        if (neighbor.rssi < link[1]){
                            link[1] = neighbor.rssi;
                            link[0].setMap(null);
                            link[0] = createPolyline(lineCoordinates, neighbor.rssi);
                        }
                    } // create link if it does not already exists
                    else {
                        var l = createPolyline(lineCoordinates, neighbor.rssi);
                        LINKS.push([l, neighbor.rssi]);
                    }
                }
            }
        }
    }
}

function setDate(){
    var date = $("#datepicker").val();
    var time = $("#timepicker").val();
    var utcTime = new Date(date + " " + time).toISOString();
    noLoop = 0;
    load_data(utcTime, noLoop);
}

//----------------Interface Listeners ---------------------------------------//

$(document).ready(function() {
    $("#next_time").click(function(event) {
        var selectedTime =  $('#timepicker').timepicker('getTimeAsDate');
        // add 5 minutes
        var newDate = new Date(selectedTime.getTime() + 5*60000)
        str_date = newDate.getHours().toString() + ":" + newDate.getMinutes().toString();
        $('#timepicker').timepicker('setTime', str_date);
        setDate();
    });
});

$(document).ready(function() {
    $("#prev_time").click(function(event) {
        var selectedTime =  $('#timepicker').timepicker('getTimeAsDate');
        // remove 5 minutes
        var newDate = new Date(selectedTime.getTime() - 5*60000)
        str_date = newDate.getHours().toString() + ":" + newDate.getMinutes().toString();
        $('#timepicker').timepicker('setTime', str_date);
        setDate();
    });
});

//------------------ Helpers ------------------------------------------------//

function clearLinks(){
    // remove links
    for (var i=0; i<LINKS.length; i++) {
        if (i in LINKS){
            LINKS[i][0].setMap(null);
        }
    }
    LINKS = [];
    LINKS.length = 0;
}

function getLinkColor(rssi){
    if (rssi>GOOD_LINK_LIMIT)
        return GOOD_LINK_COLOR;
    else if ( rssi >= MEDIUM_LINK_LIMIT && rssi <= GOOD_LINK_LIMIT)
        return MEDIUM_LINK_COLOR;
    else
        return BAD_LINK_COLOR;
}

function udpateMote(mac, lat, lng){
    var moteId = null;
    for (var i=0; i<MOTES.length; i++) {
        if (i in MOTES){
            if (MOTES[i][0] == mac){
                if (MOTES[i][1] == null){
                    MOTES[i][1] = createMarker(lat, lng, mac);
                } else if (MOTES[i][1].position.lat() != lat ||
                            MOTES[i][1].position.lng() != lng) {
                    MOTES[i][1].setMap(null);
                    MOTES[i][1] = createMarker(lat, lng, mac);
                }
            }
        }
    }
}

function createMarker(lat, lng, content){
    // create Markers
    var myLatLng = new google.maps.LatLng(lat, lng)
    var marker = new google.maps.Marker({
        position: myLatLng,
        map: map,
    });
    // add popup listener
    infoBox(map, marker, content);
    return marker;
}

function createPolyline(lineCoordinates, rssi){
    var color = getLinkColor(rssi);
    var line = new google.maps.Polyline({
          path: lineCoordinates,
          geodesic: true,
          strokeColor: color,
          strokeOpacity: 1.0,
          strokeWeight: 2
    });
    line.setMap(map);
    infoBox(map, line, rssi.toString());
    return line;
}

function getLink(LatLng1, LatLng2){
    for (i=0; i<LINKS.length; i++) {
        link = LINKS[i][0];
        var coord1 = "("+link.getPath().getAt(0).lat()+", "+link.getPath().getAt(0).lng()+")"
        var coord2 = "("+link.getPath().getAt(1).lat()+", "+link.getPath().getAt(1).lng()+")"
        if ( ((LatLng1.toString() == coord1) && (LatLng2.toString() == coord2)) ||
             ((LatLng2.toString() == coord1) && (LatLng1.toString() == coord2))
           ){
            return LINKS[i]
        }
    }
    return null
}

function markerExists(LatLng){
    for (i in MOTES) {
        if (MOTES[i][0].getPosition().toString() == LatLng.toString())
          return 1;
    }
    return 0;
}

function getLocationFromId(moteId){
    if (MOTES[moteId][1] != null)
        return MOTES[moteId][1].position;
    else
        return null
}

function getLocationFromMac(mac){
    for( i=0; i<MOTES.length; i++ ) {
        if (i in MOTES && MOTES[i][0] == mac){
            return MOTES[i][1].position;
        }
    }
    console.log("MAC not found:" + mac)
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
    });
}

function pad2(s_num) {
    i_num = s_num.parseInt()
    p_num = (i_num < 10 ? '0' : '') + i_num
    return p_num.toString()
}

