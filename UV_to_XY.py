# Author- Carl Bass
# Date - 2024-02-17
# Description- Fusion add-in that maps a surfaces parametric (u,v) space to (x,y) coordinates

import adsk.core, adsk.fusion, adsk.cam, traceback
import os

# Global list to keep all event handlers in scope.
handlers = []

# global variables available in all functions
app = adsk.core.Application.get()
ui  = app.userInterface

# global variables because I can't find a better way to pass this info around -- would be nice if fusion api had some cleaner way to do this
debug = True
chordal_deviation = 0.1
scale_factor = 1.

def run(context):
    try:
        global tool_diameter

        # Find where the python file lives and look for the icons in the ./.resources folder
        python_file_folder = os.path.dirname(os.path.realpath(__file__))
        resource_folder = os.path.join (python_file_folder, '.resources')

        # Get the CommandDefinitions collection so we can add a command
        command_definitions = ui.commandDefinitions

        tooltip = 'Maps lines, arcs and fitted splines from sketch to surface'

        # Create a button command definition.
        uv_xy_button = command_definitions.addButtonDefinition('UV_to_XY', 'UV to XY', tooltip, resource_folder)
        
        # Connect to the command created event.
        uv_xy_command_created = command_created()
        uv_xy_button.commandCreated.add (uv_xy_command_created)
        handlers.append(uv_xy_command_created)

        # add the Moose Tools and the xy to uv button to the Tools tab
        utilities_tab = ui.allToolbarTabs.itemById('ToolsTab')
        if utilities_tab:
            # get or create the "Moose Tools" panel.
            moose_tools_panel = ui.allToolbarPanels.itemById('MoosePanel')
            if not moose_tools_panel:
                moose_tools_panel = utilities_tab.toolbarPanels.add('MoosePanel', 'Moose Tools')

        if moose_tools_panel:
            # Add the command to the panel.
            control = moose_tools_panel.controls.addCommand(uv_xy_button)
            control.isPromoted = False
            control.isPromotedByDefault = False
            debug_print ('Moose Tools installed and control added')
    except:
        if ui:
            ui.messageBox('Failed:\n{}'.format(traceback.format_exc()))

# Event handler for the commandCreated event.
class command_created (adsk.core.CommandCreatedEventHandler):
    def __init__(self):
        super().__init__()
    def notify(self, args):
        try:
            event_args = adsk.core.CommandCreatedEventArgs.cast(args)
            command = event_args.command
            inputs = command.commandInputs
    
            # Connect to the execute event.
            on_execute = command_executed()
            command.execute.add(on_execute)
            handlers.append(on_execute)

            # create the face selection input
            face_selection_input = inputs.addSelectionInput('face_select', 'Face', 'Select the face')
            face_selection_input.addSelectionFilter('Faces')
            face_selection_input.setSelectionLimits(1,1)

            inputs.addFloatSpinnerCommandInput ('chordal_deviation', 'Chordal deviation', 'in', 0.1 , 1.0 , .05, chordal_deviation)

            inputs.addFloatSpinnerCommandInput ('scale_factor', 'Sketch scale factor', '', 0.01 , 100.0 , 1, scale_factor)

            # create debug checkbox
            inputs.addBoolValueInput('debug', 'Debug', True, '', False)
        except:
            ui.messageBox('Failed:\n{}'.format(traceback.format_exc()))

# Event handler for the execute event.
class command_executed (adsk.core.CommandEventHandler):
    def __init__(self):
        super().__init__()
    def notify(self, args):
        global debug
        global chordal_deviation
        global scale_factor

        try:
            design = app.activeProduct

            # get current command
            command = args.firingEvent.sender

            for input in command.commandInputs:
                if (input.id == 'face_select'):
                    face = input.selection(0).entity
                elif (input.id == 'chordal_deviation'):
                    chordal_deviation = input.value       
                elif (input.id == 'scale_factor'):
                    scale_factor = input.value    
                elif (input.id == 'debug'):
                    debug = input.value                      
                else:
                    debug_print (f'OOOPS --- too much input')

            root_component = design.rootComponent
            sketches = root_component.sketches

            parent_body = face.body

            output_sketch = sketches.add (root_component.xYConstructionPlane)
            output_sketch.name = f'UV to XY'
            sketch_points = output_sketch.sketchPoints

            edges = face.edges

            for e in edges:
                (status, start_p, end_p) = e.evaluator.getParameterExtents()

                (status, points) = e.evaluator.getStrokes (start_p, end_p, chordal_deviation)

                (status, params) = face.evaluator.getParametersAtPoints(points)
                
                uvp = adsk.core.Point3D.create (0.0, 0.0, 0.0)
                for uv in params:
                    uvp.x = uv.x * scale_factor
                    uvp.y = uv.y * scale_factor
                    sketch_points.add (uvp)

        except:
            ui.messageBox('Failed:\n{}'.format(traceback.format_exc()))	


def debug_print (msg):
    if debug:
        text_palette = ui.palettes.itemById('TextCommands')
        text_palette.writeText (msg)
        
def stop(context):
    try:
        # clean up the UI
        command_definitions = ui.commandDefinitions.itemById('UV_to_XY')
        if command_definitions:
            command_definitions.deleteMe()
        
        # get rid of this button
        moose_tools_panel = ui.allToolbarPanels.itemById('MoosePanel')
        control = moose_tools_panel.controls.itemById('UV_to_XY')
        if control:
            control.deleteMe()

        # and if it's the last button, get rid of the moose panel
        if moose_tools_panel.controls.count == 0:
                    moose_tools_panel.deleteMe()

    except:
        if ui:
            ui.messageBox('Failed:\n{}'.format(traceback.format_exc()))	
