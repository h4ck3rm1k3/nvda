#NVDAObjects/excel.py
#A part of NonVisual Desktop Access (NVDA)
#Copyright (C) 2006-2007 NVDA Contributors <http://www.nvda-project.org/>
#This file is covered by the GNU General Public License.
#See the file COPYING for more details.

from comtypes import COMError
import comtypes.automation
import wx
import re
import oleacc
import ui
import config
import textInfos
import colors
import eventHandler
import gui
import winUser
import controlTypes
from . import Window
from .. import NVDAObjectTextInfo
import scriptHandler

xlA1 = 1
xlRC = 2

re_RC=re.compile(r'R(?:\[(\d+)\])?C(?:\[(\d+)\])?')

class ExcelBase(Window):
	"""A base that all Excel NVDAObjects inherit from, which contains some useful methods."""

	@staticmethod
	def excelWindowObjectFromWindow(windowHandle):
		try:
			pDispatch=oleacc.AccessibleObjectFromWindow(windowHandle,winUser.OBJID_NATIVEOM,interface=comtypes.automation.IDispatch)
		except (COMError,WindowsError):
			return None
		return comtypes.client.dynamic.Dispatch(pDispatch)

	@staticmethod
	def getCellAddress(cell, external=False,format=xlA1):
		return cell.Address(False, False, format, external)

	def fireFocusOnSelection(self):
		selection=self.excelWindowObject.Selection
		if selection.Count>1:
			obj=ExcelSelection(windowHandle=self.windowHandle,excelWindowObject=self.excelWindowObject,excelRangeObject=selection)
		else:
			obj=ExcelCell(windowHandle=self.windowHandle,excelWindowObject=self.excelWindowObject,excelCellObject=selection)
		eventHandler.executeEvent("gainFocus",obj)

class Excel7Window(ExcelBase):
	"""An overlay class for Window for the EXCEL7 window class, which simply bounces focus to the active excel cell."""

	def _get_excelWindowObject(self):
		return self.excelWindowObjectFromWindow(self.windowHandle)

	def event_gainFocus(self):
		self.fireFocusOnSelection()

class ExcelWorksheet(ExcelBase):

	role=controlTypes.ROLE_TABLE

	def __init__(self,windowHandle=None,excelWindowObject=None,excelWorksheetObject=None):
		self.excelWindowObject=excelWindowObject
		self.excelWorksheetObject=excelWorksheetObject
		super(ExcelWorksheet,self).__init__(windowHandle=windowHandle)
		for gesture in self.__changeSelectionGestures:
			self.bindGesture(gesture, "changeSelection")

	def _get_name(self):
		return self.excelWorksheetObject.name

	def _isEqual(self, other):
		if not super(ExcelWorksheet, self)._isEqual(other):
			return False
		return self.excelWorksheetObject.index == other.excelWorksheetObject.index

	def _get_firstChild(self):
		cell=self.excelWorksheetObject.cells(1,1)
		return ExcelCell(windowHandle=self.windowHandle,excelWindowObject=self.excelWindowObject,excelCellObject=cell)

	def script_changeSelection(self,gesture):
		gesture.send()
		if scriptHandler.isScriptWaiting():
			# Prevent lag if keys are pressed rapidly.
			return
		self.fireFocusOnSelection()
	script_changeSelection.canPropagate=True

	__changeSelectionGestures = (
		"kb:tab",
		"kb:shift+tab",
		"kb:upArrow",
		"kb:downArrow",
		"kb:leftArrow",
		"kb:rightArrow",
		"kb:control+upArrow",
		"kb:control+downArrow",
		"kb:control+leftArrow",
		"kb:control+rightArrow",
		"kb:home",
		"kb:end",
		"kb:control+home",
		"kb:control+end",
		"kb:shift+upArrow",
		"kb:shift+downArrow",
		"kb:shift+leftArrow",
		"kb:shift+rightArrow",
		"kb:shift+control+upArrow",
		"kb:shift+control+downArrow",
		"kb:shift+control+leftArrow",
		"kb:shift+control+rightArrow",
		"kb:shift+home",
		"kb:shift+end",
		"kb:shift+control+home",
		"kb:shift+control+end",
		"kb:shift+space",
		"kb:control+space",
		"kb:control+pageUp",
		"kb:control+pageDown",
		"kb:control+v",
	)

class ExcelCellTextInfo(NVDAObjectTextInfo):

	def _getFormatFieldAndOffsets(self,offset,formatConfig,calculateOffsets=True):
		formatField=textInfos.FormatField()
		fontObj=self.obj.excelCellObject.font
		if formatConfig['reportFontName']:
			formatField['font-name']=fontObj.name
		if formatConfig['reportFontSize']:
			formatField['font-size']=str(fontObj.size)
		if formatConfig['reportFontAttributes']:
			formatField['bold']=fontObj.bold
			formatField['italic']=fontObj.italic
			formatField['underline']=fontObj.underline
		if formatConfig['reportColor']:
			try:
				formatField['color']=colors.RGB.fromCOLORREF(int(fontObj.color))
			except COMError:
				pass
			try:
				formatField['background-color']=colors.RGB.fromCOLORREF(int(self.obj.excelCellObject.interior.color))
			except COMError:
				pass
		return formatField,(self._startOffset,self._endOffset)

class ExcelCell(ExcelBase):

	columnHeaderRows={}
	rowHeaderColumns={}

	def _get_columnHeaderText(self):
		tableID=self.tableID
		rowNumber=self.rowNumber
		columnNumber=self.columnNumber
		columnHeaderRow=self.columnHeaderRows.get(tableID) or None
		if columnHeaderRow and rowNumber>columnHeaderRow:
			return self.excelCellObject.parent.cells(columnHeaderRow,columnNumber).text

	def _get_rowHeaderText(self):
		tableID=self.tableID
		rowNumber=self.rowNumber
		columnNumber=self.columnNumber
		rowHeaderColumn=self.rowHeaderColumns.get(tableID) or None
		if rowHeaderColumn and columnNumber>rowHeaderColumn:
			return self.excelCellObject.parent.cells(rowNumber,rowHeaderColumn).text

	def script_setColumnHeaderRow(self,gesture):
		scriptCount=scriptHandler.getLastScriptRepeatCount()
		tableID=self.tableID
		if not config.conf['documentFormatting']['reportTableHeaders']:
			# Translators: a message reported in the SetColumnHeaderRow script for Excel.
			ui.message(_("Cannot set headers. Please enable reporting of table headers in Document Formatting Settings"))
			return
		if scriptCount==0:
			self.columnHeaderRows[tableID]=self.rowNumber
			# Translators: a message reported in the SetColumnHeaderRow script for Excel.
			ui.message(_("Set column header row"))
		elif scriptCount==1 and tableID in self.columnHeaderRows:
			del self.columnHeaderRows[tableID]
			# Translators: a message reported in the SetColumnHeaderRow script for Excel.
			ui.message(_("Cleared column header row"))
	script_setColumnHeaderRow.__doc__=_("Pressing once will set the current row as the row where column headers should be found. Pressing twice clears the setting.")

	def script_setRowHeaderColumn(self,gesture):
		scriptCount=scriptHandler.getLastScriptRepeatCount()
		tableID=self.tableID
		if not config.conf['documentFormatting']['reportTableHeaders']:
			# Translators: a message reported in the SetRowHeaderColumn script for Excel.
			ui.message(_("Cannot set headers. Please enable reporting of table headers in Document Formatting Settings"))
			return
		if scriptCount==0:
			self.rowHeaderColumns[tableID]=self.columnNumber
			# Translators: a message reported in the SetRowHeaderColumn script for Excel.
			ui.message(_("Set row header column"))
		elif scriptCount==1 and tableID in self.rowHeaderColumns:
			del self.rowHeaderColumns[tableID]
			# Translators: a message reported in the SetRowHeaderColumn script for Excel.
			ui.message(_("Cleared row header column"))
	script_setRowHeaderColumn.__doc__=_("Pressing once will set the current column as the column where row headers should be found. Pressing twice clears the setting.")

	@classmethod
	def kwargsFromSuper(cls,kwargs,relation=None):
		windowHandle=kwargs['windowHandle']
		excelWindowObject=cls.excelWindowObjectFromWindow(windowHandle)
		if not excelWindowObject:
			return False
		if isinstance(relation,tuple):
			excelCellObject=excelWindowObject.rangeFromPoint(relation[0],relation[1])
		else:
			excelCellObject=excelWindowObject.ActiveCell
		if not excelCellObject:
			return False
		kwargs['excelWindowObject']=excelWindowObject
		kwargs['excelCellObject']=excelCellObject
		return True

	def __init__(self,windowHandle=None,excelWindowObject=None,excelCellObject=None):
		self.excelWindowObject=excelWindowObject
		self.excelCellObject=excelCellObject
		super(ExcelCell,self).__init__(windowHandle=windowHandle)

	role=controlTypes.ROLE_TABLECELL

	TextInfo=ExcelCellTextInfo

	def _isEqual(self,other):
		if not super(ExcelCell,self)._isEqual(other):
			return False
		thisAddr=self.getCellAddress(self.excelCellObject,True)
		try:
			otherAddr=self.getCellAddress(other.excelCellObject,True)
		except COMError:
			#When cutting and pasting the old selection can become broken
			return False
		return thisAddr==otherAddr

	name=None

	def _get_cellCoordsText(self):
		return self.getCellAddress(self.excelCellObject) 

	def _get__rowAndColumnNumber(self):
		rc=self.excelCellObject.address(False,False,xlRC,False)
		return [int(x)+1 if x else 1 for x in re_RC.match(rc).groups()]

	def _get_rowNumber(self):
		return self._rowAndColumnNumber[0]

	def _get_columnNumber(self):
		return self._rowAndColumnNumber[1]

	def _get_tableID(self):
		address=self.excelCellObject.address(1,1,0,1)
		ID="".join(address.split('!')[:-1])
		ID="%s %s"%(ID,self.windowHandle)
		return ID

		
	def _get_value(self):
		return self.excelCellObject.Text

	def _get_description(self):
		# Translators: This is presented in Excel when the current cell contains a formula.
		return _("has formula") if self.excelCellObject.HasFormula else ""

	def _get_parent(self):
		worksheet=self.excelCellObject.Worksheet
		return ExcelWorksheet(windowHandle=self.windowHandle,excelWindowObject=self.excelWindowObject,excelWorksheetObject=worksheet)

	def _get_next(self):
		try:
			next=self.excelCellObject.next
		except COMError:
			next=None
		if next:
			return ExcelCell(windowHandle=self.windowHandle,excelWindowObject=self.excelWindowObject,excelCellObject=next)

	def _get_previous(self):
		try:
			previous=self.excelCellObject.previous
		except COMError:
			previous=None
		if previous:
			return ExcelCell(windowHandle=self.windowHandle,excelWindowObject=self.excelWindowObject,excelCellObject=previous)

	__gestures = {
		"kb:NVDA+shift+c": "setColumnHeaderRow",
		"kb:NVDA+shift+r": "setRowHeaderColumn",
	}

class ExcelSelection(ExcelBase):

	role=controlTypes.ROLE_TABLECELL

	def __init__(self,windowHandle=None,excelWindowObject=None,excelRangeObject=None):
		self.excelWindowObject=excelWindowObject
		self.excelRangeObject=excelRangeObject
		super(ExcelSelection,self).__init__(windowHandle=windowHandle)

	def _get_states(self):
		states=super(ExcelSelection,self).states
		states.add(controlTypes.STATE_SELECTED)
		return states

	def _get_name(self):
		firstCell=self.excelRangeObject.Item(1)
		lastCell=self.excelRangeObject.Item(self.excelRangeObject.Count)
		# Translators: This is presented in Excel to show the current selection, for example 'a1 c3 through a10 c10'
		return _("{firstAddress} {firstContent} through {lastAddress} {lastContent}").format(firstAddress=self.getCellAddress(firstCell),firstContent=firstCell.Text,lastAddress=self.getCellAddress(lastCell),lastContent=lastCell.Text)

	def _get_parent(self):
		worksheet=self.excelRangeObject.Worksheet
		return ExcelWorksheet(windowHandle=self.windowHandle,excelWindowObject=self.excelWindowObject,excelWorksheetObject=worksheet)

	#Its useful for an excel selection to be announced with reportSelection script
	def makeTextInfo(self,position):
		if position==textInfos.POSITION_SELECTION:
			position=textInfos.POSITION_ALL
		return super(ExcelSelection,self).makeTextInfo(position)
