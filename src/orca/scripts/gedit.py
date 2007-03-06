# Orca
#
# Copyright 2004-2006 Sun Microsystems Inc.
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Library General Public
# License as published by the Free Software Foundation; either
# version 2 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Library General Public License for more details.
#
# You should have received a copy of the GNU Library General Public
# License along with this library; if not, write to the
# Free Software Foundation, Inc., 59 Temple Place - Suite 330,
# Boston, MA 02111-1307, USA.

"""Custom script for gedit."""

__id__        = "$Id$"
__version__   = "$Revision$"
__date__      = "$Date$"
__copyright__ = "Copyright (c) 2005-2006 Sun Microsystems Inc."
__license__   = "LGPL"

import orca.debug as debug
import orca.atspi as atspi
import orca.braille as braille
import orca.default as default
import orca.orca as orca
import orca.orca_state as orca_state
import orca.rolenames as rolenames
import orca.speech as speech
import orca.speechgenerator as speechgenerator
import orca.util as util

from orca.orca_i18n import _

########################################################################
#                                                                      #
# The GEdit script class.                                              #
#                                                                      #
########################################################################

class SpeechGenerator(speechgenerator.SpeechGenerator):
    """Overrides _getSpeechForFrame so as to avoid digging into the
    gedit hierarchy and tickling a bug in gedit.
    """
    def __init__(self, script):
        speechgenerator.SpeechGenerator.__init__(self, script)

    def _getSpeechForFrame(self, obj, already_focused):
        """Get the speech for a frame.  [[[TODO: WDW - This avoids
        digging into the component hierarchy so as to avoid tickling
        a bug in GEdit (see module comment above).]]]

        Arguments:
        - obj: the frame
        - already_focused: if False, the obj just received focus

        Returns a list of utterances to be spoken for the object.
        """

        utterances = self._getDefaultSpeech(obj, already_focused)

        # This will dig deep into the hierarchy, causing issues with
        # gedit.  So, we won't do this.
        #
        #utterances = self._getSpeechForAlert(obj, already_focused)

        self._debugGenerator("GEditSpeechGenerator._getSpeechForFrame",
                             obj,
                             already_focused,
                             utterances)

        return utterances

class Script(default.Script):

    def __init__(self, app):
        """Creates a new script for the given application.

        Arguments:
        - app: the application to create a script for.
        """

        default.Script.__init__(self, app)

        # Set the debug level for all the methods in this script.
        #
        self.debugLevel = debug.LEVEL_FINEST

        # This will be used to cache a handle to the gedit text area for
        # spell checking purposes.

        self.textArea = None

        # The following variables will be used to try to determine if we've
        # already handled this misspelt word (see readMisspeltWord() for
        # more details.

        self.lastCaretPosition = -1
        self.lastBadWord = ''
        self.lastEventType = ''

    def getSpeechGenerator(self):
        """Returns the speech generator for this script.
        """
        return SpeechGenerator(self)

    def readMisspeltWord(self, event, panel):
        """Speak/braille the current misspelt word plus its context.
           The spell check dialog contains a "paragraph" which shows the
           context for the current spelling mistake. After speaking/brailling
           the default action for this component, that a selection of the
           surronding text from that paragraph with the misspelt word is also
           spoken.

        Arguments:
        - event: the event.
        - panel: the panel in the check spelling dialog containing the label
                 with the misspelt word.
        """

        # Braille the default action for this component.
        #
        self.updateBraille(orca_state.locusOfFocus)

        # Look for the label containing the misspelled word.
        # There will be three labels in the top panel in the Check
        # Spelling dialog. Look for the one that isn't a label to
        # another component.
        #
        allLabels = self.findByRole(panel, rolenames.ROLE_LABEL)
        for i in range(0, len(allLabels)):
            if allLabels[i].name.startswith(_("Change to:")) or \
               allLabels[i].name.startswith(_("Misspelled word:")):
                continue
            else:
                badWord = allLabels[i].name
                break

        # Note that we often get two or more of these focus or property-change
        # events each time there is a new misspelt word. We extract the
        # current text caret position and the misspelt word and compare
        # them against the values saved from the last time this routine
        # was called. If they are the same then we ignore it.

        if self.textArea != None:
            allText = self.findByRole(self.textArea, rolenames.ROLE_TEXT)
            caretPosition = allText[0].text.caretOffset

            debug.println(self.debugLevel, \
                "gedit.readMisspeltWord: type=%s  word=%s caret position=%d" \
                % (event.type, badWord, caretPosition))

            if (caretPosition == self.lastCaretPosition) and \
               (badWord == self.lastBadWord) and \
               (event.type == self.lastEventType):
                return

            # The indication that spell checking is complete is when the
            # "misspelt" word is set to "Completed spell checking". Ugh!
            # Try to detect this and let the user know.

            if badWord == _("Completed spell checking"):
                utterance = _("Spell checking is complete.")
                speech.speak(utterance)
                utterance = _("Press Tab and Return to terminate.")
                speech.speak(utterance)
                return

            # If we have a handle to the gedit text area, then extract out
            # all the text objects, and create a list of all the words found
            # in them.
            #
            allTokens = []
            for i in range(0, len(allText)):
                text = self.getText(allText[i], 0, -1)
                tokens = text.split()
                allTokens += tokens

            self.speakMisspeltWord(allTokens, badWord)

            # Save misspelt word information for comparison purposes
            # next time around.
            #
            self.lastCaretPosition = caretPosition
            self.lastBadWord = badWord
            self.lastEventType = event.type

    def isFocusOnFindDialog(self):
        """Return an indication of whether the current locus of focus is on
        the Find button or the combo box in the Find dialog.
        """

        obj = orca_state.locusOfFocus
        rolesList1 = [rolenames.ROLE_PUSH_BUTTON,
                     rolenames.ROLE_FILLER,
                     rolenames.ROLE_FILLER,
                     rolenames.ROLE_DIALOG,
                     rolenames.ROLE_APPLICATION]

        rolesList2 = [rolenames.ROLE_COMBO_BOX,
                     rolenames.ROLE_PANEL,
                     rolenames.ROLE_FILLER,
                     rolenames.ROLE_FILLER,
                     rolenames.ROLE_DIALOG,
                     rolenames.ROLE_APPLICATION]

        if (self.isDesiredFocusedItem(obj, rolesList1) \
            and obj.name == _("Find")) \
            or (self.isDesiredFocusedItem(obj, rolesList2) \
                and obj.parent.parent.parent.parent.name == _("Find")):
            return True
        else:
            return False

    # This method tries to detect and handle the following cases:
    # 1) Text area (for caching handle for spell checking purposes).
    # 2) Check Spelling Dialog.

    def locusOfFocusChanged(self, event, oldLocusOfFocus, newLocusOfFocus):
        """Called when the visual object with focus changes.

        Arguments:
        - event: if not None, the Event that caused the change
        - oldLocusOfFocus: Accessible that is the old locus of focus
        - newLocusOfFocus: Accessible that is the new locus of focus
        """

        brailleGen = self.brailleGenerator
        speechGen = self.speechGenerator

        debug.printObjectEvent(self.debugLevel,
                               event,
                               event.source.toString())

        # self.printAncestry(event.source)

        # 1) Text area (for caching handle for spell checking purposes).
        #
        # This works in conjunction with code in section 2). Check to see if
        # focus is currently in the gedit text area. If it is, then, if this
        # is the first time, save a pointer to the scroll pane which contains
        # the text being editted.
        #
        # Note that this drops through to then use the default event
        # processing in the parent class for this "focus:" event.

        rolesList = [rolenames.ROLE_TEXT,
                     rolenames.ROLE_SCROLL_PANE,
                     rolenames.ROLE_FILLER,
                     rolenames.ROLE_PAGE_TAB,
                     rolenames.ROLE_PAGE_TAB_LIST,
                     rolenames.ROLE_SPLIT_PANE]
        if self.isDesiredFocusedItem(event.source, rolesList):
            debug.println(self.debugLevel,
                          "gedit.locusOfFocusChanged - text area.")

            self.textArea = event.source.parent
            # Fall-thru to process the event with the default handler.

        # 2) check spelling dialog.
        #
        # Check to see if the Spell Check dialog has just appeared and got
        # focus. If it has, then speak/braille the current misspelt word
        # plus its context.
        #
        # Note that in order to make sure that this focus event is for the
        # check spelling dialog, a check is made of the localized name of the
        # option pane. Translators for other locales will need to ensure that
        # their translation of this string matches what gedit uses in
        # that locale.

        rolesList = [rolenames.ROLE_TEXT,
                     rolenames.ROLE_FILLER,
                     rolenames.ROLE_PANEL,
                     rolenames.ROLE_FILLER,
                     rolenames.ROLE_FRAME]
        if self.isDesiredFocusedItem(event.source, rolesList):
            frame = event.source.parent.parent.parent.parent
            if frame.name.startswith(_("Check Spelling")):
                debug.println(self.debugLevel,
                        "gedit.locusOfFocusChanged - check spelling dialog.")

                self.readMisspeltWord(event, event.source.parent.parent)
                # Fall-thru to process the event with the default handler.

        # For everything else, pass the focus event onto the parent class
        # to be handled in the default way.

        default.Script.locusOfFocusChanged(self, event,
                                           oldLocusOfFocus, newLocusOfFocus)

    # This method tries to detect and handle the following cases:
    # 1) check spelling dialog.
    # 2) find dialog - phrase not found.

    def onNameChanged(self, event):
        """Called whenever a property on an object changes.

        Arguments:
        - event: the Event
        """

        brailleGen = self.brailleGenerator
        speechGen = self.speechGenerator

        debug.printObjectEvent(self.debugLevel,
                               event,
                               event.source.toString())

        # self.printAncestry(event.source)

        # 1) check spelling dialog.
        #
        # Check to see if if we've had a property-change event for the
        # accessible name for the label containing the current misspelt
        # word in the check spelling dialog.
        # This (hopefully) means that the user has just corrected a
        # spelling mistake, in which case, speak/braille the current
        # misspelt word plus its context.
        #
        # Note that in order to make sure that this event is for the
        # check spelling dialog, a check is made of the localized name of the
        # frame. Translators for other locales will need to ensure that
        # their translation of this string matches what gedit uses in
        # that locale.

        rolesList = [rolenames.ROLE_LABEL,
                     rolenames.ROLE_PANEL,
                     rolenames.ROLE_FILLER,
                     rolenames.ROLE_FRAME]
        if self.isDesiredFocusedItem(event.source, rolesList):
            frame = event.source.parent.parent.parent
            if frame.name.startswith(_("Check Spelling")):
                debug.println(self.debugLevel,
                      "gedit.onNameChanged - check spelling dialog.")

                self.readMisspeltWord(event, event.source.parent)
                # Fall-thru to process the event with the default handler.

        # 2) find dialog - phrase not found.
        #
        # If we've received an "object:property-change:accessible-name" for
        # the status bar and the current locus of focus is on the Find
        # button on the Find dialog or the combo box in the Find dialog
        # and the last input event was a Return and the name for the current
        # event source is "Phrase not found", then speak it.
        #
        # [[[TODO: richb - "Phrase not found" is spoken twice because we
        # apparently get two identical "object:property-change:accessible-name"
        # events.]]]

        if event.source.role == rolenames.ROLE_STATUSBAR \
           and self.isFocusOnFindDialog() \
           and orca_state.lastInputEvent.event_string == "Return" \
           and event.source.name == _("Phrase not found"):
                debug.println(self.debugLevel,
                              "gedit.onNameChanged - phrase not found.")

                speech.speak(event.source.name)

        # Pass the event onto the parent class to be handled in the default way.
        default.Script.onNameChanged(self, event)

    def onStateChanged(self, event):
        """Called whenever an object's state changes.

        Arguments:
        - event: the Event
        """

        # Sometimes an object will tell us it is focused this
        # way versus issuing a focus event.  GEdit's edit area,
        # for example, will do this: when you use metacity's
        # window menu to do things like maximize or unmaximize
        # a window, you will only get a state-changed event
        # from the text area when it regains focus.
        # (See bug #350854 for more details).
        #
        if (event.type == "object:state-changed:focused") \
           and (event.detail1):
            orca.setLocusOfFocus(event, event.source)

        default.Script.onStateChanged(self, event)

    # This method tries to detect and handle the following cases:
    # 1) find dialog - phrase found.

    def onCaretMoved(self, event):
        """Called whenever the caret moves.

        Arguments:
        - event: the Event
        """

        debug.printObjectEvent(self.debugLevel,
                               event,
                               event.source.toString())

        # self.printAncestry(event.source)

        # If we've received a text caret moved event and the current locus
        # of focus is on the Find button on the Find dialog or the combo
        # box in the Find dialog and the last input event was a Return,
        # and if the current line contains the phrase we were looking for,
        # then speak the current text line, to give an indication of what
        # we've just found.
        #
        if self.isFocusOnFindDialog() \
           and orca_state.lastInputEvent.event_string == "Return":
            debug.println(self.debugLevel, "gedit.onCaretMoved - find dialog.")

            allComboBoxes = self.findByRole(orca_state.locusOfFocus.app,
                                            rolenames.ROLE_COMBO_BOX)
            phrase = self.getDisplayedText(allComboBoxes[0])
            [text, caretOffset, startOffset] = \
                self.getTextLineAtCaret(event.source)
            if text.lower().find(phrase) != -1:
                speech.speak(_("Phrase found."))
                utterances = self.speechGenerator.getSpeech(event.source, True)
                speech.speakUtterances(utterances)

        # For everything else, pass the caret moved event onto the parent
        # class to be handled in the default way.

        default.Script.onCaretMoved(self, event)
