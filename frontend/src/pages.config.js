import Dashboard from './pages/Dashboard';
import TaskWarRoom from './pages/TaskWarRoom';
import __Layout from './Layout.jsx';


export const PAGES = {
    "Dashboard": Dashboard,
    "TaskWarRoom": TaskWarRoom,
}

export const pagesConfig = {
    mainPage: "Dashboard",
    Pages: PAGES,
    Layout: __Layout,
};