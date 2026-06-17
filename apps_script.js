// VORTEX 動画ログ + Google Drive自動保存
// Apps Scriptに貼り付けて「デプロイ」→「デプロイを管理」→新しいバージョンでデプロイ

function doPost(e) {
  var sheet = SpreadsheetApp.getActiveSpreadsheet().getActiveSheet();
  var data = JSON.parse(e.postData.contents);

  // ヘッダー行がなければ追加
  if (sheet.getLastRow() === 0) {
    sheet.appendRow([
      "動画", "日付", "アカウント", "トピック",
      "SLIDE_1（フック）", "SLIDE_2", "SLIDE_3", "SLIDE_4", "SLIDE_5（CTA）",
      "ナレーション"
    ]);
    // ヘッダー行を太字・背景色
    var header = sheet.getRange(1, 1, 1, 10);
    header.setFontWeight("bold");
    header.setBackground("#1a1a2e");
    header.setFontColor("#ffffff");
    sheet.setFrozenRows(1);
  }

  // Google Driveに動画を保存してURLを取得
  var driveUrl = "";
  if (data.video_url && data.video_url !== "") {
    driveUrl = uploadToDrive(data.video_url, data.account, data.date);
  }

  // Sheetsに追記（動画リンクを最初の列に）
  var videoCell = driveUrl
    ? '=HYPERLINK("' + driveUrl + '","▶ 再生")'
    : (data.video_url ? '=HYPERLINK("' + data.video_url + '","⬇ DL")' : "");

  sheet.appendRow([
    videoCell,
    data.date,
    data.account,
    data.topic,
    data.slide_1  || "",
    data.slide_2  || "",
    data.slide_3  || "",
    data.slide_4  || "",
    data.slide_5  || "",
    data.narration || ""
  ]);

  // 列幅を自動調整
  sheet.autoResizeColumns(1, 4);

  return ContentService
    .createTextOutput(JSON.stringify({ ok: true, drive_url: driveUrl }))
    .setMimeType(ContentService.MimeType.JSON);
}

// Google Driveに動画をアップロードして共有URLを返す
function uploadToDrive(videoUrl, account, date) {
  try {
    var rootFolder = getOrCreateFolder("VORTEX Videos");
    var dateFolder = getOrCreateFolder(date, rootFolder);
    var accountFolder = getOrCreateFolder(account, dateFolder);

    // 同名ファイルが既にあれば削除
    var filename = account + "_" + date + ".mp4";
    var existing = accountFolder.getFilesByName(filename);
    while (existing.hasNext()) { existing.next().setTrashed(true); }

    // 動画をダウンロードしてDriveに保存
    var response = UrlFetchApp.fetch(videoUrl, { muteHttpExceptions: true });
    if (response.getResponseCode() !== 200) {
      Logger.log("動画取得失敗: " + response.getResponseCode());
      return "";
    }

    var blob = response.getBlob().setName(filename).setContentType("video/mp4");
    var file = accountFolder.createFile(blob);

    // リンクを知っている全員が閲覧可能に
    file.setSharing(DriveApp.Access.ANYONE_WITH_LINK, DriveApp.Permission.VIEW);

    return file.getUrl();
  } catch (e) {
    Logger.log("Driveアップロードエラー: " + e.toString());
    return "";
  }
}

// フォルダを取得または作成
function getOrCreateFolder(name, parent) {
  var folders = parent
    ? parent.getFoldersByName(name)
    : DriveApp.getFoldersByName(name);
  if (folders.hasNext()) return folders.next();
  return parent
    ? parent.createFolder(name)
    : DriveApp.createFolder(name);
}
