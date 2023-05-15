import stable_whisper
import sys
import time
import re

# some element IDs
winID = "com.blackmagicdesign.resolve.AutoSubsGen"   # should be unique for single instancing
textID = "TextEdit"
trackID = "TrackSelector"
wordsID = "MaxWords"
charsID = "MaxChars"
addSubsID = "AddSubs"
generateSubsID = "GenSubs"
browseFilesID = "BrowseButton"

ui = fusion.UIManager
dispatcher = bmd.UIDispatcher(ui)
storagePath = fusion.MapPath(r"Scripts:/Utility/")

# check for existing instance
win = ui.FindWindow(winID)
if win:
   win.Show()
   win.Raise()
   exit()
# otherwise, we set up a new window

# define the window UI layout
win = dispatcher.AddWindow({
   'ID': winID,
   'Geometry': [ 100,100, 400, 620 ],
   'WindowTitle': "Resolve Auto Subtitle Generator",
   },
   ui.VGroup([
      ui.Label({ 'Text': "Transcribe Timeline", 'Weight': 0, 'Font': ui.Font({ 'PixelSize': 22 }) }),
      ui.Label({ 'Text': "Max words per line", 'Weight': 0, 'Font': ui.Font({ 'PixelSize': 13 }) }),
      ui.SpinBox({"ID": "MaxWords", "Min": 1, "Value": 5}),
      ui.VGap(2),
      ui.Label({ 'Text': "Max characters per line", 'Weight': 0, 'Font': ui.Font({ 'PixelSize': 13 }) }),
      ui.SpinBox({"ID": "MaxChars", "Min": 1, "Value": 18}),
      ui.VGap(4),
      ui.Button({ 'ID': generateSubsID, 'Text': "Transcribe", 'MinimumSize': [150, 25], 'MaximumSize': [1000, 30]}),
      ui.VGap(10),
      ui.Label({ 'Text': "Generate Text+ Subtitles", 'Weight': 0, 'Font': ui.Font({ 'PixelSize': 22 }) }),
      ui.Label({ 'Text': "Select track to add subtitles", 'Weight': 0, 'Font': ui.Font({ 'PixelSize': 13 }) }),
      ui.SpinBox({"ID": "TrackSelector", "Min": 1, "Value": 3}),
      ui.CheckBox({"ID": "UseCustomSRT", "Text": "Use Custom .SRT Subtitles File", "Checked": False}),
      ui.CheckBox({"ID": "NoCapitals", "Text": "Make each line lowercase", "Checked": False}),
      ui.VGap(2),
      ui.Label({'ID': 'Label', 'Text': 'Select a custom SRT subtitles file', 'Weight': 0, 'Font': ui.Font({ 'PixelSize': 13 }) }),
      ui.HGroup({'Weight': 0.0,},[
			ui.LineEdit({'ID': 'FileLineTxt', 'Text': '', 'PlaceholderText': 'Please Enter a filepath', 'Weight': 0.9}),
			ui.Button({'ID': 'BrowseButton', 'Text': 'Browse', 'Weight': 0.1}),
		]),
      ui.VGap(2),
      ui.Label({'ID': 'Label', 'Text': 'Words to censor (comma separated list)', 'Weight': 0, 'Font': ui.Font({ 'PixelSize': 13 }) }),
      ui.LineEdit({'ID': 'CensorList', 'Text': '', 'PlaceholderText': 'e.g kill, shot (k**l)', 'Weight': 0}),
      ui.VGap(4),
      ui.Button({ 'ID': addSubsID,  'Text': "Add Subs to Timeline", 'MinimumSize': [150, 25], 'MaximumSize': [1000, 30]}),
      ui.VGap(26),
      ui.Label({ 'ID': 'DialogBox', 'Text': "No Task Started", 'Weight': 0, 'Font': ui.Font({ 'PixelSize': 18 }), 'Alignment': { 'AlignHCenter': True } }),
      ui.VGap(22)
      ])
   )

itm = win.GetItems()

# Event handlers
def OnClose(ev):
   dispatcher.ExitLoop()

def OnBrowseFiles(ev):
	selectedPath = fusion.RequestFile()
	if selectedPath:
		itm['FileLineTxt'].Text = str(selectedPath)

def OnAddSubs(ev):
   projectManager = resolve.GetProjectManager()
   project = projectManager.GetCurrentProject()
   mediaPool = project.GetMediaPool()
   if not project:
       print("No project is loaded")
       sys.exit()
   # Get current timeline. If no current timeline try to load it from timeline list
   timeline = project.GetCurrentTimeline()
   if not timeline:
       if project.GetTimelineCount() > 0:
          timeline = project.GetTimelineByIndex(1)
          project.SetCurrentTimeline(timeline)
   if not timeline:
       print("Current project has no timelines")
       sys.exit()
   else:
      if win.Find(trackID).Value > timeline.GetTrackCount('video'):
         print("Track not found - Please select a valid track")
         itm['DialogBox'].Text = "Please select a valid track!"
         return
      
      # CHOOSE SRT FILE
      if itm["UseCustomSRT"].Checked == True and itm['FileLineTxt'].Text != '':
         file_path = r"{}".format(itm['FileLineTxt'].Text)
         print("Using custom subtitles from -> [", file_path, "]")
      else:
         file_path = storagePath + 'audio.srt'
      
      # READ SRT FILE
      try:
         with open(file_path, 'r') as f:
            lines = f.readlines()
      except FileNotFoundError:
         print("No subtitles file (audio.srt) found - Please Transcribe the timeline or load your own SRT file!")
         itm['DialogBox'].Text = "No subtitles found!"
         return

      # PARSE SRT FILE
      subs = []
      checkCensor = False
      if itm['CensorList'].Text != '': # only check for swear words if list is not empty
            swear_words = itm['CensorList'].Text.split(',')
            checkCensor = True
      for i in range(0, len(lines), 4):
         frame_rate = timeline.GetSetting("timelineFrameRate") # get timeline framerate
         start_time, end_time = lines[i+1].strip().split(" --> ")
         text = lines[i+2].strip() # get  subtitle text
         if checkCensor: # check for swear words
            for word in swear_words:
               pattern = r"\b" + re.escape(word) + r"\b"
               censored_word = word[0] + '*' * (len(word) - 2) + word[-1]
               text = re.sub(pattern, censored_word, text, flags=re.IGNORECASE)
               pattern = re.escape(word)
               censored_word = word[0] + '**'
               text = re.sub(pattern, censored_word, text, flags=re.IGNORECASE)
               if itm['NoCapitals'].Checked: # make each line lowercase
                  text = text.lower()
         # Convert timestamps to frames set postition of subtitle
         hours, minutes, seconds_milliseconds = start_time.split(':')
         seconds, milliseconds = seconds_milliseconds.split(',')
         frames = int(round((int(hours) * 3600 + int(minutes) * 60 + int(seconds) + int(milliseconds) / 1000) * frame_rate))
         timelinePos = frames + timeline.GetStartFrame()
         # Set duration of subtitle in frames
         hours, minutes, seconds_milliseconds = end_time.split(':')
         seconds, milliseconds = seconds_milliseconds.split(',')
         frames = int(round((int(hours) * 3600 + int(minutes) * 60 + int(seconds) + int(milliseconds) / 1000) * frame_rate))
         duration = frames - timelinePos
         subs.append([timelinePos, duration, text])
      
      # ADD TEXT+ TO TIMELINE
      folder = mediaPool.GetRootFolder()
      items = folder.GetClipList()
      foundText = False
      for item in items:
         if item.GetName() == "Text+": # Find Text+ in Media Pool
            foundText = True
            print("Found Text+ in Media Pool")
            print("Adding template subtitles")
            itm['DialogBox'].Text = "Adding template subtitles..."
            for i in range(len(subs)):
               timelinePos, duration, text = subs[i]
               if i < len(subs)-1 and subs[i+1][0] - (timelinePos + duration) < 200: # if gap between subs is less than 10 frames
                  duration = (subs[i+1][0] - subs[i][0]) - 1 # set duration to next start frame -1 frame
               timelineTrack = win.Find(trackID).Value # set video track
               newClip = {
                  "mediaPoolItem" : item,
                  "startFrame" : 0,
                  "endFrame" : duration,
                  "trackIndex" : timelineTrack,
                  "recordFrame" : timelinePos
               }
               mediaPool.AppendToTimeline( [newClip] ) # Add Text+ to timeline
            projectManager.SaveProject()
            
            subList = timeline.GetItemListInTrack('video', 3)
            print("Updating text content")
            itm['DialogBox'].Text = "Updating text content..."
            for i, sub in enumerate(subList):
               sub.SetClipColor('Orange')
               comp = sub.GetFusionCompByIndex(1)
               toollist = comp.GetToolList().values()
               for tool in toollist:
                   if tool.GetAttrs()['TOOLS_Name'] == 'Template' :
                       comp.SetActiveTool(tool)
                       tool.SetInput('StyledText', subs[i][2])
               sub.SetClipColor('Teal')
               if i == len(subList)-1:
                  print("Finished updating text content")
                  itm['DialogBox'].Text = "Finished updating text content"
                  break
            break # only execute once if multiple Text+ in Media Pool
      if not foundText:
         print("Text+ not found in Media Pool")
   projectManager.SaveProject()
   itm['DialogBox'].Text = "Subtitles added to timeline!"


def OnGenSubs(ev):
   projectManager = resolve.GetProjectManager()
   project = projectManager.GetCurrentProject()
   project.LoadRenderPreset("Audio Only")
   project.SetRenderSettings({"SelectAllFrames": 0, "CustomName": "audio", "TargetDir": storagePath})
   pid = project.AddRenderJob()
   project.StartRendering(pid)
   print("Rendering Audio for Transcription...")
   itm['DialogBox'].Text = "Rendering Audio for Transcription..."
   while project.IsRenderingInProgress():
      time.sleep(1)
      progress = project.GetRenderJobStatus(pid).get("CompletionPercentage")
      print("Progress: ", progress, "%")
      itm['DialogBox'].Text = "Progress: ", progress, "%"
   print("Audio Rendering Complete!")
   itm['DialogBox'].Text = "Audio Rendering Complete!"
   filename = "audio.mp3"
   location = storagePath + filename
   #file_path = r'S:\Blackmagic Design\DaVinci Resolve\Fusion\Scripts\Utility\'
   print("Transcribing -> [", filename, "]")
   itm['DialogBox'].Text = "Transcribing ", filename
   model = stable_whisper.load_model("small.en")
   result = model.transcribe(location, fp16=False, language='en', regroup=False) # transcribe audio file
   (
       result
       .split_by_punctuation([('.', ' '), '。', '?', '？', ',', '，'])
       .split_by_gap(.5)
       .merge_by_gap(.10, max_words=3)
       .split_by_length(max_words=win.Find(wordsID).Value, max_chars=win.Find(charsID).Value)
   )
   file_path = storagePath + 'audio.srt'
   result.to_srt_vtt(file_path, word_level=False) # save to SRT file
   print("Transcription Complete!")
   itm['DialogBox'].Text = "Transcription Complete!"
   print("Subtitles saved to -> [", file_path, "]")
   print("Click 'Add Subs to Timeline' to add to timeline")
   resolve.OpenPage("edit")

# assign event handlers
win.On[winID].Close     = OnClose
win.On[addSubsID].Clicked  = OnAddSubs
win.On[generateSubsID].Clicked = OnGenSubs
win.On[browseFilesID].Clicked = OnBrowseFiles

# Main dispatcher loop
win.Show()
dispatcher.RunLoop()