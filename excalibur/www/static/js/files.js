// https://coderwall.com/p/flonoa/simple-string-format-in-javascript
String.prototype.format = function () {
  var str = this;
  for (var i in arguments) {
    str = str.replace(new RegExp('\\{' + i + '\\}', 'gm'), arguments[i]);
  }
  return str;
}

$(document).ready(function () {
  $('#file').on('change',function (){
    // get the file name
    const filename = document.getElementById("file").files[0].name;
    // replace the "Choose file..." label
    $(this).next('.uploadFile__label').html(filename);
  })

  $('#upload').on('click', function () {
    var data = new FormData();
    // TODO: add support to upload multiple files
    $.each($('#file')[0].files, function (i, file) {
      data.append('file-' + i, file);
    });
    var pages = $('#pages').val() ? $('#pages').val() : 1;
    var agency = $('#agency').val() ? $('#agency').val() : "";
    data.append('pages', pages);
    data.append('agency', agency);
    $.ajax({
      url: '/files',
      type: 'POST',
      cache: false,
      contentType: false,
      data: data,
      processData: false,
      success: function (data) {
        var redirect = '{0}//{1}/workspaces/{2}'.format(window.location.protocol, window.location.host, data['file_id']);
        window.location.replace(redirect);
      }
    });
  });

  $("#search").on("keyup", function() {
    var regex = new RegExp($(this).val().toLowerCase());
    $("#filtertable tr").removeClass('active');
    $("#filtertable tr").show().filter(function() {
      $(this).toggle(regex.test($(this).text().toLowerCase()))
    });
    paginate('new_data',50);
    paginate('read_data',50);
    paginate('ignored_data',50);
  });

  paginate('new_data',50);
  paginate('read_data',50);
  paginate('ignored_data',50);
  
  function paginate(tableName,RecordsPerPage) {
    $('#nav'+tableName).remove();
    $('#'+tableName + ' tbody tr:visible').addClass('active');
    $('#'+tableName).after('<div id="nav'+tableName+'"></div>');
    var rowsShown = RecordsPerPage;
    var rowsTotal = $('#'+tableName + ' tbody tr.active').length;
    var numPages = rowsTotal / rowsShown;
    for (i = 0; i < numPages; i++) {
        var pageNum = i + 1;
        $('#nav'+tableName).append('<a href="#" rel="' + i + '">' + pageNum + '</a> ');
    }
    $('#'+tableName + ' tbody tr.active').hide();
    $('#'+tableName + ' tbody tr.active').slice(0, rowsShown).show();
    $('#nav'+tableName+' a:first').addClass('active');
    $('#nav'+tableName+' a').bind('click', function (e) {
      e.preventDefault();
      $('#nav'+tableName+' a').removeClass('active');
      $(this).addClass('active');
      var currPage = $(this).attr('rel');
      var startItem = currPage * rowsShown;
      var endItem = startItem + rowsShown;
      $('#'+tableName + ' tbody tr.active').hide().slice(startItem, endItem).
        css('display', 'table-row').animate({ opacity: 1 }, 300);
    });
  }

});
