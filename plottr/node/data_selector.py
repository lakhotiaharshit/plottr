"""
data_selector.py

A node and widget for subselecting from a dataset.
"""
from typing import List, Tuple, Dict

from plottr import QtGui, QtCore
from .node import Node, NodeWidget, updateOption
from ..data.datadict import DataDictBase
from ..gui.data_display import DataSelectionWidget
from ..utils import num

__author__ = 'Wolfgang Pfaff'
__license__ = 'MIT'


class DataDisplayWidget(NodeWidget):
    """
    Simple Tree widget to show data and their dependencies in the node data.
    """

    def __init__(self, node: Node = None):
        super().__init__(embedWidgetClass=DataSelectionWidget)

        self.optSetters = {
            'selectedData': self.setSelected,
        }
        self.optGetters = {
            'selectedData': self.getSelected,
        }

        self.widget.dataSelectionMade.connect(
            lambda x: self.signalOption('selectedData'))

    def setSelected(self, vals: List[str]):
        self.widget.setSelectedData(vals)
        self._updateOptions(vals)

    def getSelected(self) -> List[str]:
        return self.widget.getSelectedData()

    def setData(self, data: DataDictBase):
        self.widget.setData(data)

    def setShape(self, shapes: Dict[str, Tuple[int, ...]]):
        self.widget.setShape(shapes)

    def _updateOptions(self, selected):
        ds = self.widget._dataStructure
        for n, w in self.widget.checkBoxes.items():
            if selected != [] and ds[n]['axes'] != ds[selected[0]]['axes']:
                self.widget.setItemEnabled(n, False)
            else:
                self.widget.setItemEnabled(n, True)


class DataSelector(Node):
    """
    This node allows extracting data from datasets. The fields specified by
    ``selectedData`` and their axes are kept, the rest is discarded.
    All selected data fields must be compatible in the sense that they have the
    same axes (also in the same order).
    The utility of this node is that afterwards data can safely be processed
    together, as the structure of all remaining fields is shared.

    Properties of this node:
    :selectedData: list of strings with compatible dependents.
    """

    # TODO: allow the user to control dtypes.

    nodeName = "DataSelector"
    uiClass = DataDisplayWidget

    newDataStructure = QtCore.pyqtSignal(object)
    dataShapeChanged = QtCore.pyqtSignal(object)

    force_numerical_data = True

    def __init__(self, *arg, **kw):
        super().__init__(*arg, **kw)

        self._dataStructure = None
        self.selectedData = []

    # Properties

    @property
    def selectedData(self) -> List[str]:
        return self._selectedData

    @selectedData.setter
    @updateOption('selectedData')
    def selectedData(self, val: List[str]):
        if isinstance(val, str):
            val = [val]
        self._selectedData = val

    # Data processing

    def validateOptions(self, data):
        """
        Validations performed:
        * only compatible data fields can be selected.
        """
        if data is None:
            return True

        for elt in self.selectedData:
            if elt not in data:
                self.logger().warning(
                    f'Did not find selected data {elt} in data. '
                    f'Clearing the selection.'
                )
                self._selectedData = []

        if len(self.selectedData) > 0:
            allowed_axes = data.axes(self.selectedData[0])
            for d in self.selectedData:
                if data.axes(d) != allowed_axes:
                    self.logger().error(
                        f'Datasets {self.selectedData[0]} '
                        f'(with axes {allowed_axes}) '
                        f'and {d}(with axes {data.axes(d)}) are not compatible '
                        f'and cannot be selected simultaneously.'
                        )
                    return False
        return True

    def _reduceData(self, data):
        if isinstance(self.selectedData, str):
            dnames = [self.selectedData]
        else:
            dnames = self.selectedData
        if len(self.selectedData) == 0:
            return None

        ret = data.extract(dnames)
        if self.force_numerical_data:
            for d, _ in ret.data_items():
                dt = num.largest_numtype(ret.data_vals(d),
                                         include_integers=False)
                if dt is not None:
                    ret[d]['values'] = ret[d]['values'].astype(dt)
                else:
                    return None

        return ret

    def process(self, **kw):
        data = super().process(**kw)
        if data is None:
            return None
        data = data['dataOut']

        # this is for the UI
        struct = data.structure()
        if not DataDictBase.same_structure(struct, self._dataStructure):
            self._dataStructure = struct
            self.newDataStructure.emit(struct)
        self.dataShapeChanged.emit(data.shapes())

        # this is the actual operation of the node
        data = self._reduceData(data)
        if data is None:
            return None

        return dict(dataOut=data)

    # Methods for GUI interaction

    def setupUi(self):
        super().setupUi()
        self.newDataStructure.connect(self.ui.setData)
        self.dataShapeChanged.connect(self.ui.setShape)

